let API_BASE = (() => {
  try {
    const qs = new URLSearchParams(window.location.search);
    const param = qs.get('api');
    if (param) {
      localStorage.setItem('x7_api_base', param);
    }
    const saved = localStorage.getItem('x7_api_base');
    const env = (typeof window !== 'undefined' && (window.API_BASE || window.__API_BASE__)) || saved;
    if (env) return ('' + env).replace(/\/$/, '');
    const loc = window.location;
    return `${loc.protocol}//${loc.host}/api/v1`;
  } catch {
    return 'http://localhost:8000/api/v1';
  }
})();

const els = {
  messages: document.getElementById('messages'),
  input: document.getElementById('input'),
  send: document.getElementById('sendBtn'),
  actions: document.getElementById('quickActions'),
  statusDot: document.getElementById('statusDot'),
  connectBtn: document.getElementById('connectBtn'),
  dedicatedToggle: document.getElementById('dedicatedToggle'),
  businessId: document.getElementById('businessId'),
};

let ws = null;
let sessionId = getOrCreateSessionId();
let isDedicated = false;
let reconnectAttempts = 0;
let reconnectTimer = null;
const MAX_RECONNECT_DELAY = 15000;

// Streaming state
let streamBuffer = "";       // committed/plain text currently shown in the bubble
let streamEl = null;          // DOM node of the current streaming bubble
let streamLi = null;          // parent <li> for adding/removing typing class
let playbackQueue = [];       // incoming characters waiting to be rendered
let playbackTimer = null;     // current setTimeout handle
let playing = false;          // whether playback loop is running

(async () => { await init(); })();

// Configure Markdown rendering if available
if (window.marked) {
  try {
    marked.setOptions({ gfm: true, breaks: true });
  } catch {}
}

async function init() {
  renderSystem('New session: ' + sessionId);
  // Ensure API base points to a live backend
  await ensureApiBase();
  // Restore UI state
  try {
    const savedDedicated = localStorage.getItem('x7_dedicated') === '1';
    isDedicated = savedDedicated;
    els.dedicatedToggle.checked = savedDedicated;
    els.businessId.disabled = !savedDedicated;
    const savedBiz = localStorage.getItem('x7_business_id');
    if (savedBiz) els.businessId.value = savedBiz;
  } catch {}
  els.dedicatedToggle.addEventListener('change', onToggleDedicated);
  els.businessId.addEventListener('input', onBizInput);
  els.connectBtn.addEventListener('click', connectWS);
  els.send.addEventListener('click', onSend);
  els.input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  });

  // Auto-connect on load
  connectWS();
}

// --- Streaming helpers (character-by-character) ---
function ensureStreamBubble() {
  if (streamEl) return;
  const li = document.createElement('li');
  li.className = 'msg bot';
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = '';
  li.appendChild(bubble);
  const ts = document.createElement('div');
  ts.className = 'timestamp';
  ts.innerText = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  li.appendChild(ts);
  els.messages.appendChild(li);
  els.messages.scrollTop = els.messages.scrollHeight;
  streamEl = bubble;
  streamLi = li;
  // show caret while typing
  try { streamLi.classList.add('typing'); } catch {}
}

function handleCharStream(chunk) {
  if (!chunk) return;
  ensureStreamBubble();
  // push incoming characters into playback queue
  for (let i = 0; i < chunk.length; i++) playbackQueue.push(chunk[i]);
  startPlayback();
}

function startPlayback() {
  if (playing) return;
  playing = true;
  scheduleNextTick();
}

function scheduleNextTick() {
  if (!streamEl) ensureStreamBubble();
  if (playbackTimer) { clearTimeout(playbackTimer); playbackTimer = null; }
  if (playbackQueue.length === 0) {
    playing = false;
    return;
  }
  const ch = playbackQueue.shift();
  streamBuffer += ch;
  if (streamEl) {
    streamEl.textContent = streamBuffer;
    els.messages.scrollTop = els.messages.scrollHeight;
  }
  const delay = delayFor(ch);
  playbackTimer = setTimeout(scheduleNextTick, delay);
}

function delayFor(ch) {
  // base jitter for natural feel
  const jitter = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min;
  if (ch === '\n') return 230 + jitter(40, 100);
  if (/[\.\!\?]/.test(ch)) return 240 + jitter(80, 160);
  if (/[,;:]/.test(ch)) return 140 + jitter(50, 120);
  if (ch === ' ') return 20 + jitter(10, 40);
  return 34 + jitter(10, 26);
}

function finalizeAssistantMessage(finalText, actions) {
  ensureStreamBubble();
  // stop any ongoing playback
  if (playbackTimer) { try { clearTimeout(playbackTimer); } catch {} playbackTimer = null; }
  playing = false;
  // prefer backend-provided final text if present
  const text = finalText != null ? finalText : (streamBuffer + playbackQueue.join(''));
  playbackQueue = [];
  if (window.marked && window.DOMPurify) {
    streamEl.innerHTML = DOMPurify.sanitize(marked.parse(text || ''));
    try {
      streamEl.querySelectorAll('a').forEach(a => {
        a.setAttribute('target', '_blank');
        a.setAttribute('rel', 'noopener noreferrer');
      });
    } catch {}
  } else {
    streamEl.textContent = text || '';
  }
  streamBuffer = '';
  // remove typing caret
  try { if (streamLi) streamLi.classList.remove('typing'); } catch {}
  streamEl = null;
  streamLi = null;
  if (actions && Array.isArray(actions)) {
    renderActions(actions);
  }
}

function onToggleDedicated(e) {
  isDedicated = e.target.checked;
  els.businessId.disabled = !isDedicated;
  try { localStorage.setItem('x7_dedicated', isDedicated ? '1' : '0'); } catch {}
}

function onBizInput() {
  try { localStorage.setItem('x7_business_id', els.businessId.value || ''); } catch {}
}

function getOrCreateSessionId() {
  const key = 'x7_chat_session_id';
  let id = localStorage.getItem(key);
  if (!id) {
    id = crypto.randomUUID ? crypto.randomUUID() : uuidv4();
    localStorage.setItem(key, id);
  }
  return id;
}

function connectWS() {
  cleanupWS();
  const url = new URL(API_BASE);
  const wsScheme = url.protocol === 'https:' ? 'wss' : 'ws';
  const origin = `${wsScheme}://${url.host}`;

  let path;
  if (isDedicated) {
    const biz = parseInt(els.businessId.value, 10);
    if (!biz) {
      notify('Enter a Business ID for dedicated chat');
      return;
    }
    path = `/api/v1/dedicated-chat/ws/${biz}/${sessionId}`;
  } else {
    path = `/api/v1/chat/ws/${sessionId}`;
  }

  const wsUrl = origin + path;
  ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    setConnStatus(true);
    notify('Connected');
    if (reconnectTimer) { try { clearTimeout(reconnectTimer); } catch {} reconnectTimer = null; }
    reconnectAttempts = 0;
  };
  ws.onclose = () => {
    setConnStatus(false);
    notify('Disconnected');
    scheduleReconnect();
  };
  ws.onerror = (err) => {
    console.error('WS error', err);
    notify('WebSocket error');
  };
  ws.onmessage = (evt) => {
    (async () => {
      const raw = typeof evt.data === 'string' ? evt.data : await evt.data.text();
      try {
        const data = JSON.parse(raw);
        switch (data.type) {
          case 'connected':
            renderSystem(data.message || 'Connected');
            break;
          case 'typing':
          case 'typing_start':
          case 'typing_chunk':
            // streaming disabled in UI; ignore
            break;
          case 'typing_complete':
            finalizeAssistantMessage(data.message || '', data.suggested_actions || []);
            break;
          case 'message':
            finalizeAssistantMessage(data.message || '', data.suggested_actions || []);
            break;
          case 'suggested_actions':
            if (data.data) renderActions(data.data);
            break;
          case 'metadata':
            // no-op in UI for now
            break;
          case 'error':
            renderSystem('Error: ' + (data.message || 'Unknown'));
            break;
          default:
            if (data.message) {
              finalizeAssistantMessage(data.message, data.suggested_actions || []);
            }
            break;
        }
      } catch {
        // Non-JSON frame -> treat as streamed chunk
        // streaming disabled; ignore raw chunks
      }
    })();
  };
}

function cleanupWS() {
  if (ws) {
    try { ws.close(); } catch {}
    ws = null;
  }
  setConnStatus(false);
}

async function ensureApiBase() {
  const candidates = [];
  // Current configured base
  candidates.push(API_BASE);
  // Common local backends
  candidates.push('http://localhost:8000/api/v1');
  candidates.push('http://127.0.0.1:8000/api/v1');

  for (const base of Array.from(new Set(candidates))) {
    const ok = await pingHealth(base);
    if (ok) {
      if (API_BASE !== base) {
        API_BASE = base;
        try { localStorage.setItem('x7_api_base', base); } catch {}
        renderSystem('Using API: ' + base);
      }
      return;
    }
  }
  renderSystem('Could not reach API at ' + API_BASE + '. Set ?api=http://localhost:8000/api/v1 and reload.');
}

async function pingHealth(base) {
  try {
    const origin = base.replace(/\/api\/v1$/, '');
    const res = await fetch(origin + '/health', { method: 'GET' });
    return res.ok;
  } catch {
    return false;
  }
}

function scheduleReconnect() {
  if (reconnectTimer) return;
  const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), MAX_RECONNECT_DELAY);
  reconnectAttempts++;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connectWS();
  }, delay);
}

async function onSend() {
  const text = els.input.value.trim();
  if (!text) return;
  els.input.value = '';
  renderUser(text);

  // Prefer WS
  if (ws && ws.readyState === WebSocket.OPEN) {
    const context = {};
    try {
      ws.send(JSON.stringify({ message: text, context, stream: false }));
    } catch (e) {
      console.error('WS send failed, falling back to HTTP', e);
      await sendViaHttp(text);
    }
  } else {
    await sendViaHttp(text);
  }
}

async function sendViaHttp(text) {
  try {
    let url = `${API_BASE}/chat/message`;
    let body = { message: text, session_id: sessionId, context: { channel: 'web' } };

    if (isDedicated) {
      const biz = parseInt(els.businessId.value, 10);
      if (!biz) {
        notify('Enter a Business ID for dedicated chat');
        return;
      }
      url = `${API_BASE}/dedicated-chat/message/${biz}`;
      body = { message: text, session_id: sessionId, context: { channel: 'dedicated_web', selected_business: biz } };
    }

    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      if (res.status === 413) {
        renderSystem('The message/context was too large. Please try a shorter message.');
        return;
      }
      throw new Error('HTTP ' + res.status);
    }
    const data = await res.json();
    renderBot(data.message || '');
    renderActions(data.suggested_actions || []);
  } catch (e) {
    console.error(e);
    renderSystem('Failed to send. Check API is running on ' + API_BASE);
  }
}

function renderActions(actions) {
  els.actions.innerHTML = '';
  const normalized = actions.map(a => {
    if (typeof a === 'string') return { id: a, title: a };
    if (a && typeof a === 'object') return { id: a.id || a.title || 'action', title: a.title || a.id || '' };
    return null;
  }).filter(Boolean);

  normalized.forEach(a => {
    const btn = document.createElement('button');
    btn.className = 'action-btn';
    btn.textContent = a.title;
    btn.addEventListener('click', () => handleQuickAction(a));
    els.actions.appendChild(btn);
  });
}

function handleQuickAction(action) {
  // For now, just send the title as text; include action id in context for backend if WS
  const text = action.title;
  renderUser(text);
  const payload = { message: text, context: { clicked_action: action.id }, stream: false };
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(payload));
  } else {
    // HTTP fallback
    sendViaHttp(text);
  }
}

function renderUser(text) { renderMessage('user', text, false); }
function renderBot(text) { renderMessage('bot', text, true); }
function renderSystem(text) { renderMessage('system', text, false); }

function renderMessage(role, text, markdown = false) {
  const li = document.createElement('li');
  li.className = 'msg ' + (role === 'user' ? 'user' : 'bot');

  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  if (markdown && window.marked && window.DOMPurify) {
    bubble.innerHTML = DOMPurify.sanitize(marked.parse(text || ''));
    // Ensure links open safely in a new tab
    try {
      bubble.querySelectorAll('a').forEach(a => {
        a.setAttribute('target', '_blank');
        a.setAttribute('rel', 'noopener noreferrer');
      });
    } catch {}
  } else {
    bubble.innerText = text;
  }

  const ts = document.createElement('div');
  ts.className = 'timestamp';
  ts.innerText = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  li.appendChild(bubble);
  li.appendChild(ts);
  els.messages.appendChild(li);
  els.messages.scrollTop = els.messages.scrollHeight;
}

function setConnStatus(on) {
  els.statusDot.classList.toggle('on', !!on);
  els.statusDot.classList.toggle('off', !on);
  els.statusDot.title = on ? 'Connected' : 'Disconnected';
}

function notify(msg) {
  renderSystem(msg);
}

// Fallback UUIDv4
function uuidv4() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0, v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}
