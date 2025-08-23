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
    // Always point to backend server on port 8000
    return 'http://localhost:8000/api/v1';
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
let playbackQueue = [];       // incoming characters/words waiting to be rendered
let playbackTimer = null;     // current setTimeout handle
let playing = false;          // whether playback loop is running
let isTyping = false;         // track typing state to prevent duplicate events

// Set to store received message IDs to prevent duplicates
const receivedMessageIds = new Set();
// Map to store message content hashes to prevent content duplicates
const receivedMessageHashes = new Map();

// Generate a simple hash for message content
function getMessageHash(content) {
  if (!content) return '';
  let hash = 0;
  for (let i = 0; i < content.length; i++) {
    const char = content.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32bit integer
  }
  return hash.toString();
}

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
    const savedBiz = localStorage.getItem('x7_business_id');
    if (savedBiz) els.businessId.value = savedBiz;
  } catch {}
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
  if (streamEl) return streamEl;
  const li = document.createElement('li');
  li.className = 'msg bot typing';
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = '';
  li.appendChild(bubble);
  els.messages.appendChild(li);
  els.messages.scrollTop = els.messages.scrollHeight;
  streamEl = bubble;
  streamLi = li;
  return streamEl;
  // show caret while typing
  try { streamLi.classList.add('typing'); } catch {}
}

function cleanupStreamBubble() {
  // Clean up any existing stream elements
  if (playbackTimer) { try { clearTimeout(playbackTimer); } catch {} playbackTimer = null; }
  playing = false;
  streamBuffer = '';
  playbackQueue = [];
  if (streamEl) {
    try { if (streamLi) streamLi.classList.remove('typing'); } catch {}
    streamEl = null;
    streamLi = null;
  }
}

function handleCharStream(chunk) {
  if (!chunk) return;
  ensureStreamBubble();
  // push incoming characters into playback queue
  for (let i = 0; i < chunk.length; i++) playbackQueue.push(chunk[i]);
  startPlayback();
}

// --- Word streaming helpers ---
function handleWordStream(word) {
  if (word === undefined) return;
  ensureStreamBubble();
  // push incoming word into playback queue
  playbackQueue.push(word);
  startWordPlayback();
}

function startWordPlayback() {
  if (playing) return;
  playing = true;
  scheduleNextWordTick();
}

function scheduleNextWordTick() {
  if (!streamEl) ensureStreamBubble();
  if (playbackTimer) { clearTimeout(playbackTimer); playbackTimer = null; }
  if (playbackQueue.length === 0) {
    playing = false;
    return;
  }
  const word = playbackQueue.shift();
  streamBuffer += word;
  if (streamEl) {
    streamEl.textContent = streamBuffer;
    els.messages.scrollTop = els.messages.scrollHeight;
  }
  // Add a delay between words for natural flow
  const delay = 100 + Math.random() * 50; // 100-150ms delay between words
  playbackTimer = setTimeout(scheduleNextWordTick, delay);
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

function finalizeAssistantMessage(finalText, actions, messageId) {
  // Always create a new message element instead of reusing existing ones
  cleanupStreamBubble();
  
  // Check if we already received this message ID to prevent duplicates
  if (messageId && receivedMessageIds.has(messageId)) {
    console.log('Duplicate message ID detected and prevented:', messageId);
    streamBuffer = '';
    playbackQueue = [];
    return;
  }
  
  // Add message ID to the set of received IDs
  if (messageId) {
    receivedMessageIds.add(messageId);
    // Clean up old message IDs to prevent memory leaks
    if (receivedMessageIds.size > 100) {
      const first = receivedMessageIds.values().next().value;
      receivedMessageIds.delete(first);
    }
  }
  
  // Generate content hash to prevent content duplicates
  const contentHash = getMessageHash(finalText);
  if (contentHash && receivedMessageHashes.has(contentHash)) {
    console.log('Duplicate message content detected and prevented:', contentHash);
    streamBuffer = '';
    playbackQueue = [];
    return;
  }
  
  // Add content hash to prevent future duplicates
  if (contentHash) {
    receivedMessageHashes.set(contentHash, Date.now());
    // Clean up old hashes to prevent memory leaks
    const now = Date.now();
    for (const [hash, timestamp] of receivedMessageHashes.entries()) {
      if (now - timestamp > 300000) { // 5 minutes
        receivedMessageHashes.delete(hash);
      }
    }
  }
  
  // Check if we already have a finalized message with the same content to prevent duplicates
  const lastMessage = els.messages.lastElementChild;
  if (lastMessage && lastMessage.classList.contains('bot')) {
    const lastBubble = lastMessage.querySelector('.bubble');
    if (lastBubble && lastBubble.textContent === finalText) {
      // Duplicate message detected, don't create a new one
      streamBuffer = '';
      playbackQueue = [];
      return;
    }
  }
  
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
  // Use the correct WebSocket endpoint (dedicated chat endpoint doesn't exist)
  path = `/api/v1/chat/ws/${sessionId}`;

  const wsUrl = origin + path;
  ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    setConnStatus(true);
    notify('Connected');
    if (reconnectTimer) { try { clearTimeout(reconnectTimer); } catch {} reconnectTimer = null; }
    reconnectAttempts = 0;
  };
  ws.onclose = () => {
    console.log('WebSocket connection closed');
    setConnStatus(false);
    notify('Disconnected');
    scheduleReconnect();
  };
  ws.onerror = (err) => {
    console.error('WebSocket error', err);
    notify('WebSocket error');
  };
  ws.onmessage = (evt) => {
    (async () => {
      const raw = typeof evt.data === 'string' ? evt.data : await evt.data.text();
      try {
        const data = JSON.parse(raw);
        console.log('Received WebSocket message:', data.type, data);
        switch (data.type) {
          case 'connected':
            renderSystem(data.message || 'Connected to X-SevenAI! How can I help you today?');
            break;
          case 'typing':
          case 'typing_start':
            // Start typing indicator only if not already typing
            if (!isTyping) {
              isTyping = true;
              // Ensure we have a stream bubble for typing indicator
              ensureStreamBubble();
              console.log('Started typing indicator');
            }
            break;
          case 'character':
            // Handle character-by-character streaming
            if (data.character) {
              handleCharStream(data.character);
            }
            break;
          case 'word':
            // Handle word-by-word streaming
            if (data.word !== undefined) {
              handleWordStream(data.word);
            }
            break;
          case 'typing_complete':
            console.log('Received typing_complete message:', data.message);
            // Finalize the message only if we've been streaming characters/words
            // and ensure we don't create duplicate messages
            if ((streamEl || playbackQueue.length > 0) && !streamEl?.parentElement?.classList?.contains('finalized')) {
              console.log('Finalizing assistant message:', data.message);
              finalizeAssistantMessage(data.message || data.partial_message || '', data.suggested_actions || [], data.message_id);
              // Mark the message as finalized to prevent duplicates
              if (streamEl && streamEl.parentElement) {
                streamEl.parentElement.classList.add('finalized');
              }
            } else {
              console.log('Skipping duplicate or unnecessary typing_complete message');
            }
            break;
          case 'message':
            // Create a new message bubble for each message
            cleanupStreamBubble();
            renderBot(data.message || '');
            if (data.suggested_actions && Array.isArray(data.suggested_actions)) {
              renderActions(data.suggested_actions);
            }
            break;
          case 'suggested_actions':
            if (data.data) renderActions(data.data);
            break;
          case 'typing_end':
            // End of typing indicator - clean up streaming state
            console.log('Received typing_end message');
            // Reset typing state
            isTyping = false;
            // Ensure any remaining content is finalized
            if (streamEl || playbackQueue.length > 0) {
              const finalText = streamBuffer + playbackQueue.join(' ');
              if (finalText.trim()) {
                finalizeAssistantMessage(finalText, [], null);
              }
              cleanupStreamBubble();
            }
            break;
          case 'metadata':
            // no-op in UI for now
            break;
          case 'error':
            console.error('Backend error:', data.message);
            renderSystem('Error: ' + data.message);
            break;
          default:
            console.warn('Unknown message type:', data.type, data);
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
    // Use only the regular chat endpoint - let AI handle everything
    const url = `${API_BASE}/chat/message`;
    const body = { message: text, session_id: sessionId, context: { channel: 'web' } };

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
