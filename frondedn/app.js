const API_BASE = 'http://localhost:8000/api/v1';

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

// Streaming state
let streamBuffer = "";       // committed/plain text currently shown in the bubble
let streamEl = null;          // DOM node of the current streaming bubble
let streamLi = null;          // parent <li> for adding/removing typing class
let playbackQueue = [];       // incoming characters waiting to be rendered
let playbackTimer = null;     // current setTimeout handle
let playing = false;          // whether playback loop is running

init();

// Configure Markdown rendering if available
if (window.marked) {
  try {
    marked.setOptions({ gfm: true, breaks: true });
  } catch {}
}

function init() {
  renderSystem('New session: ' + sessionId);
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
}

function onBizInput() {
  // no-op for now
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
  };
  ws.onclose = () => {
    setConnStatus(false);
    notify('Disconnected');
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
            // ignore typing events in UI
            break;
          case 'token':
            handleCharStream(data.delta || '');
            break;
          case 'message':
            finalizeAssistantMessage(data.message || '', data.suggested_actions || []);
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
        handleCharStream(raw);
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

async function onSend() {
  const text = els.input.value.trim();
  if (!text) return;
  els.input.value = '';
  renderUser(text);

  // Prefer WS
  if (ws && ws.readyState === WebSocket.OPEN) {
    const context = {};
    try {
      ws.send(JSON.stringify({ message: text, context, stream: true }));
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
    if (!res.ok) throw new Error('HTTP ' + res.status);
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
  const payload = { message: text, context: { clicked_action: action.id }, stream: true };
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
