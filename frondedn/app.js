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
  newChatBtn: document.getElementById('newChatBtn'),
  chatsList: document.getElementById('chatsList'),
  contactTitle: document.querySelector('.wa-contact'),
  businessIdInput: document.getElementById('businessIdInput'),
  dedicatedBtn: document.getElementById('dedicatedBtn'),
  dedicatedPane: document.getElementById('dedicatedPane'),
  toggleSidebarBtn: document.getElementById('toggleSidebarBtn'),
  waSidebar: document.querySelector('#waChat .wa-sidebar'),
  waThread: document.querySelector('#waChat .wa-thread'),
  overviewStats: document.getElementById('overviewStats'),
  conversationsList: document.getElementById('conversationsList'),
  liveOrdersList: document.getElementById('liveOrdersList'),
  refreshBtn: document.getElementById('refreshBtn'),
};

let ws = null;
let sessionId = getOrCreateSessionId();
let isDedicated = false;
let activeBusinessId = null;
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

// ----- Conversations management -----
const CONV_KEY = 'x7_conversations';
const ACTIVE_CONV_KEY = 'x7_active_conversation_id';
let conversations = []; // [{id,title,isDedicated,businessId,sessionId,lastMessage,updatedAt}]
let activeConversationId = null;

function readConversations() {
  try {
    const raw = sessionStorage.getItem(CONV_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch { return []; }
}

function writeConversations(list) {
  conversations = Array.isArray(list) ? list : [];
  try { sessionStorage.setItem(CONV_KEY, JSON.stringify(conversations)); } catch {}
}

function generateSessionId() {
  const hasCrypto = (typeof crypto !== 'undefined') && crypto && typeof crypto.randomUUID === 'function';
  return hasCrypto ? crypto.randomUUID() : uuidv4();
}

function createConversation({ isDedicated, businessId, title }) {
  const id = generateSessionId();
  const conv = {
    id,
    title: title || (isDedicated && businessId ? `Business ${businessId}` : 'Business Owners Chatting'),
    isDedicated: !!isDedicated,
    businessId: isDedicated ? Number(businessId) || null : null,
    sessionId: generateSessionId(),
    lastMessage: 'Ask me anything…',
    updatedAt: Date.now(),
  };
  const list = readConversations();
  list.unshift(conv);
  writeConversations(list);
  renderChatList();
  return conv;
}

function deleteConversation(id) {
  const list = readConversations().filter(c => c.id !== id);
  writeConversations(list);
  try { sessionStorage.removeItem(`x7_conv_msgs:${id}`); } catch {}
  if (activeConversationId === id) {
    const next = list[0] || createConversation({ isDedicated: false, businessId: null, title: 'Business Owners Chatting' });
    setActiveConversation(next.id, { connect: true, render: true });
  } else {
    renderChatList();
  }
}

function setActiveConversation(id, opts = {}) {
  const { connect = true, render = true } = opts;
  activeConversationId = id;
  try { sessionStorage.setItem(ACTIVE_CONV_KEY, id); } catch {}
  const conv = readConversations().find(c => c.id === id);
  if (!conv) return;
  // Retroactively derive title for existing conversations with default title
  try {
    if (!conv.isDedicated) {
      const isDefaultTitle = !conv.title || conv.title === 'Business Owners Chatting';
      if (isDefaultTitle) {
        const msgs = readConvMessages(conv.id) || [];
        const firstUser = msgs.find(m => m && m.role === 'user' && typeof m.text === 'string' && m.text.trim().length);
        if (firstUser) {
          const derived = deriveTitleFromText(firstUser.text);
          if (derived) {
            const list = readConversations();
            const idx = list.findIndex(c => c.id === conv.id);
            if (idx >= 0) {
              list[idx].title = derived;
              writeConversations(list);
            }
            conv.title = derived;
          }
        }
      }
    }
  } catch {}
  // Sync global state
  sessionId = conv.sessionId;
  isDedicated = !!conv.isDedicated;
  activeBusinessId = conv.businessId || null;
  try { sessionStorage.setItem('x7_chat_session_id', sessionId); } catch {}
  // Update header and input
  try { if (els.contactTitle) els.contactTitle.textContent = conv.title; } catch {}
  try { if (els.businessIdInput) els.businessIdInput.value = conv.businessId ? String(conv.businessId) : ''; } catch {}
  // Clear UI and load cached messages
  try { cleanupStreamBubble(); } catch {}
  try { els.messages.innerHTML = ''; } catch {}
  try { els.actions.innerHTML = ''; } catch {}
  if (render) renderChatList();
  const loaded = loadConversationMessages(conv.id);
  // put cursor in the composer
  try { if (els.input) els.input.focus(); } catch {}
  if (connect) connectWS();
}

function renderChatList() {
  const list = readConversations();
  const container = els.chatsList;
  if (!container) return;
  container.innerHTML = '';
  list.forEach(conv => {
    const row = document.createElement('div');
    row.className = 'wa-chat-item' + (conv.id === activeConversationId ? ' active' : '');
    row.style.cssText = 'padding:12px;border-bottom:1px solid #2a2f32;cursor:pointer;display:flex;align-items:center;gap:8px;';
    const info = document.createElement('div');
    info.style.cssText = 'flex:1;min-width:0;max-width:60ch;';
    const name = document.createElement('div');
    name.className = 'wa-chat-name';
    name.style.cssText = 'font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:28ch;';
    name.textContent = conv.title;
    const last = document.createElement('div');
    last.className = 'wa-chat-last';
    // fixed-width, multi-line (2) clamp preview regardless of sidebar width
    last.style.cssText = 'opacity:.7;font-size:12px;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;white-space:normal;max-width:50ch;';
    const when = new Date(conv.updatedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    // Sanitize and clamp preview to fixed length
    const raw = String(conv.lastMessage || '')
      .replace(/[\r\n]+/g, ' ')
      .replace(/\s+/g, ' ')
      .replace(/[*_`~>#\-]/g, '')
      .trim();
    const maxChars = 120;
    const preview = raw.length > maxChars ? (raw.slice(0, maxChars - 1) + '…') : raw;
    last.textContent = `${preview} · ${when}`;
    info.appendChild(name);
    info.appendChild(last);
    const del = document.createElement('button');
    del.className = 'btn btn-outline btn-sm';
    del.title = 'Delete conversation';
    del.textContent = 'Delete';
    del.addEventListener('click', (e) => { e.stopPropagation(); deleteConversation(conv.id); });
    row.appendChild(info);
    row.appendChild(del);
    row.addEventListener('click', () => setActiveConversation(conv.id, { connect: true, render: true }));
    container.appendChild(row);
  });
}

function convMsgsKey(id) { return `x7_conv_msgs:${id}`; }
function readConvMessages(id) {
  try {
    const raw = sessionStorage.getItem(convMsgsKey(id));
    return raw ? JSON.parse(raw) : [];
  } catch { return []; }
}
function writeConvMessages(id, msgs) {
  try { sessionStorage.setItem(convMsgsKey(id), JSON.stringify(msgs)); } catch {}
}

// Derive a short, human-friendly conversation title from the first user message
function deriveTitleFromText(text) {
  if (!text) return '';
  let s = String(text || '').replace(/[\r\n]+/g, ' ').replace(/\s+/g, ' ').trim();
  // Strip lightweight markdown symbols and code fences
  s = s.replace(/[`*_~>#]/g, '');
  // Remove URL schemes
  s = s.replace(/https?:\/\/\S+/gi, '').trim();
  // Cut at first sentence end if reasonably long
  const endIdx = s.search(/[.!?]/);
  if (endIdx >= 20) s = s.slice(0, endIdx);
  // Limit to first 8 words for brevity
  const words = s.split(' ').filter(Boolean);
  if (words.length > 8) s = words.slice(0, 8).join(' ');
  // Clamp to 60 chars, add ellipsis if needed
  if (s.length > 60) s = s.slice(0, 57).trimEnd() + '…';
  // Capitalize first letter
  if (s) s = s.charAt(0).toUpperCase() + s.slice(1);
  return s;
}
function addMessageToConversation(convId, role, text) {
  if (!convId || !text) return;
  const msgs = readConvMessages(convId);
  msgs.push({ role, text, ts: Date.now() });
  // cap to last 200
  if (msgs.length > 200) msgs.splice(0, msgs.length - 200);
  writeConvMessages(convId, msgs);
  // update conversation metadata
  const list = readConversations();
  const idx = list.findIndex(c => c.id === convId);
  if (idx >= 0) {
    list[idx].lastMessage = text;
    list[idx].updatedAt = Date.now();
    // If this is the first meaningful user message and the title is still default (non-dedicated), derive a topic title
    if (role === 'user' && !list[idx].isDedicated) {
      const currentTitle = String(list[idx].title || '');
      const isDefaultTitle = currentTitle === 'Business Owners Chatting' || currentTitle.trim() === '';
      if (isDefaultTitle) {
        const derived = deriveTitleFromText(text);
        if (derived) {
          list[idx].title = derived;
          // Update live header if this is the active conversation
          try { if (activeConversationId === convId && els.contactTitle) els.contactTitle.textContent = derived; } catch {}
        }
      }
    }
    writeConversations(list);
    renderChatList();
  }
}

function loadConversationMessages(convId) {
  const msgs = readConvMessages(convId);
  if (!Array.isArray(msgs) || !msgs.length) return 0;
  msgs.forEach(m => {
    if (m.role === 'user') {
      renderMessage('user', m.text, false, true);
    } else {
      renderMessage('bot', m.text, true, true);
    }
  });
  return msgs.length;
}

function initConversations() {
  conversations = readConversations();
  if (!conversations.length) {
    const conv = createConversation({ isDedicated: false, businessId: null, title: 'Business Owners Chatting' });
    activeConversationId = conv.id;
  }
  try {
    activeConversationId = sessionStorage.getItem(ACTIVE_CONV_KEY) || activeConversationId || (conversations[0] && conversations[0].id);
  } catch {}
  const active = conversations.find(c => c.id === activeConversationId) || conversations[0];
  if (active) setActiveConversation(active.id, { connect: false, render: true });
}

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

// Expose init without auto-running to avoid duplicate init with index.html
window.initChat = async function() { await init(); };

// Configure Markdown rendering if available
if (window.marked) {
  try {
    marked.setOptions({ gfm: true, breaks: true });
  } catch {}
}

async function init() {
  // Show disconnected status until WS connects
  try { setConnStatus(false); } catch {}
  // Ensure API base points to a live backend
  await ensureApiBase();
  // Expose API origin for other scripts that rely on REST root
  try { window.API_BASE_URL = API_BASE.replace(/\/api\/v1$/, ''); } catch {}
  // Restore UI state
  try {
    const savedBiz = localStorage.getItem('x7_business_id');
    if (savedBiz && els.businessIdInput) els.businessIdInput.value = savedBiz;
  } catch {}
  // Sidebar visibility management
  function setSidebarVisible(show) {
    const side = els.waSidebar;
    const thread = els.waThread;
    if (!side || !thread) return;
    if (show) {
      side.style.display = 'flex';
      // Responsive but bounded width so list items don't stretch too much
      // min 260px, target ~32vw, max 420px
      side.style.flex = '0 0 clamp(260px, 32vw, 420px)';
      side.style.maxWidth = '420px';
      side.style.minWidth = '260px';
      thread.style.flex = '1 1 auto';
      thread.style.minWidth = '0';
      if (els.toggleSidebarBtn) {
        try { els.toggleSidebarBtn.setAttribute('aria-pressed', 'true'); } catch {}
        try { els.toggleSidebarBtn.title = 'Hide history'; } catch {}
      }
      try { localStorage.removeItem('x7_sidebar_hidden'); } catch {}
    } else {
      side.style.display = 'none';
      thread.style.flex = '1 1 100%';
      thread.style.minWidth = '0';
      if (els.toggleSidebarBtn) {
        try { els.toggleSidebarBtn.setAttribute('aria-pressed', 'false'); } catch {}
        try { els.toggleSidebarBtn.title = 'Show history'; } catch {}
      }
      try { localStorage.setItem('x7_sidebar_hidden', '1'); } catch {}
    }
  }
  // Initialize conversations list before connecting
  initConversations();
  // Restore sidebar visibility
  let sidebarHidden = false;
  try { sidebarHidden = !!localStorage.getItem('x7_sidebar_hidden'); } catch {}
  setSidebarVisible(!sidebarHidden);
  // Toggle handler
  if (els.toggleSidebarBtn) {
    els.toggleSidebarBtn.addEventListener('click', () => {
      const currentlyHidden = els.waSidebar && (els.waSidebar.style.display === 'none' || getComputedStyle(els.waSidebar).display === 'none');
      setSidebarVisible(currentlyHidden);
    });
  }
  if (els.connectBtn) els.connectBtn.addEventListener('click', () => { isDedicated = false; activeBusinessId = null; connectWS(); });
  if (els.newChatBtn) els.newChatBtn.addEventListener('click', newChat);
  if (els.dedicatedBtn) els.dedicatedBtn.addEventListener('click', connectDedicatedWS);
  if (els.businessIdInput) {
    els.businessIdInput.addEventListener('input', () => {
      try { localStorage.setItem('x7_business_id', els.businessIdInput.value || ''); } catch {}
    });
    els.businessIdInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { e.preventDefault(); connectDedicatedWS(); }
    });
  }
  if (els.send) els.send.addEventListener('click', onSend);
  if (els.input) {
    els.input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        onSend();
      }
    });
  }

  // Auto-connect on load
  connectWS();

  // Initial fetch (only if containers exist)
  if (els.overviewStats) fetchDashboardOverview();
  if (els.conversationsList) fetchActiveConversations();
  if (els.liveOrdersList) fetchLiveOrders();

  // Refresh button
  if (els.refreshBtn) {
    els.refreshBtn.addEventListener('click', () => {
      if (els.overviewStats) fetchDashboardOverview();
      if (els.conversationsList) fetchActiveConversations();
      if (els.liveOrdersList) fetchLiveOrders();
    });
  }
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
  // show caret while typing
  try { streamLi.classList.add('typing'); } catch {}
  // show checking indicator initially
  showCheckingIndicator();
  return streamEl;
}

function cleanupStreamBubble() {
  // Clean up any existing stream elements
  if (playbackTimer) { try { clearTimeout(playbackTimer); } catch {} playbackTimer = null; }
  playing = false;
  streamBuffer = '';
  playbackQueue = [];
  if (streamEl || streamLi) {
    // Remove checking indicator if any
    hideCheckingIndicator();
    try { if (streamLi) streamLi.classList.remove('typing'); } catch {}
    // Remove the temporary typing bubble from the DOM to avoid duplicate elements
    try {
      if (streamLi && streamLi.parentNode) {
        streamLi.parentNode.removeChild(streamLi);
      }
    } catch {}
    streamEl = null;
    streamLi = null;
  }
}

function handleCharStream(chunk) {
  if (!chunk) return;
  ensureStreamBubble();
  // Once text starts streaming, hide checking indicator
  hideCheckingIndicator();
  // push incoming characters into playback queue
  for (let i = 0; i < chunk.length; i++) playbackQueue.push(chunk[i]);
  startPlayback();
}

// --- Word streaming helpers ---
function handleWordStream(word) {
  if (word === undefined) return;
  ensureStreamBubble();
  // Once text starts streaming, hide checking indicator
  hideCheckingIndicator();
  // push incoming word into playback queue
  playbackQueue.push(word);
  startWordPlayback();
}

function startWordPlayback() {
  if (playing) return;
  playing = true;
  scheduleNextWordTick();
}

// --- Checking indicator helpers ---
function showCheckingIndicator() {
  try {
    if (!streamEl) return;
    if (streamEl.querySelector('.checking-indicator')) return;
    const indicator = document.createElement('div');
    indicator.className = 'checking-indicator';
    indicator.setAttribute('aria-live', 'polite');
    indicator.setAttribute('role', 'status');
    const label = document.createElement('span');
    label.className = 'checking-label';
    label.textContent = 'Checking';
    const d1 = document.createElement('span'); d1.className = 'checking-dot';
    const d2 = document.createElement('span'); d2.className = 'checking-dot';
    const d3 = document.createElement('span'); d3.className = 'checking-dot';
    indicator.appendChild(label);
    indicator.appendChild(d1);
    indicator.appendChild(d2);
    indicator.appendChild(d3);
    streamEl.appendChild(indicator);
  } catch {}
}

function hideCheckingIndicator() {
  try {
    if (!streamEl) return;
    const el = streamEl.querySelector('.checking-indicator');
    if (el && el.parentNode) el.parentNode.removeChild(el);
  } catch {}
}

function scheduleNextWordTick() {
  if (!streamEl) ensureStreamBubble();
  if (playbackTimer) { clearTimeout(playbackTimer); playbackTimer = null; }
  if (playbackQueue.length === 0) {
    playing = false;
    return;
  }
  const word = playbackQueue.shift();
  let piece = String(word ?? '');
  // Normalize newline tokens
  if (piece === '\r' || piece === '\n' || piece === '\r\n') {
    streamBuffer += '\n';
  } else {
    // Markdown-friendly tweaks (space after headings and bullets)
    piece = piece.replace(/^(#{1,6})(\S)/, '$1 $2');
    if (piece === '*' || piece === '-') piece += ' ';

    const isPunctuation = /^[\.,!?:;\)\]]+$/.test(piece);
    const lastChar = streamBuffer.slice(-1);
    const needsSpaceBefore = streamBuffer.length > 0 && !/\s/.test(lastChar) && !isPunctuation;
    streamBuffer += (needsSpaceBefore ? ' ' : '') + piece;
  }
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
  
  // Generate content hash to prevent content duplicates
  const contentHash = getMessageHash(finalText);
  
  // Check if we already received this message ID to prevent duplicates
  if (messageId && receivedMessageIds.has(messageId)) {
    console.log('Duplicate message ID detected and prevented:', messageId);
    return;
  }
  
  // Check content hash to prevent content duplicates
  if (contentHash && receivedMessageHashes.has(contentHash)) {
    console.log('Duplicate message content detected and prevented:', contentHash);
    return;
  }
  
  // Check if we already have a finalized message with the same content to prevent duplicates
  const lastMessage = els.messages.lastElementChild;
  if (lastMessage && lastMessage.classList.contains('bot')) {
    const lastBubble = lastMessage.querySelector('.bubble');
    if (lastBubble && lastBubble.textContent === finalText) {
      console.log('Duplicate message content detected in DOM:', finalText);
      return;
    }
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
  
  const li = document.createElement('li');
  li.className = 'msg bot';
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = '';
  li.appendChild(bubble);
  const ts = document.createElement('div');
  ts.className = 'timestamp';
  ts.innerText = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  bubble.appendChild(ts);
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
  // Persist to active conversation
  try { if (activeConversationId) addMessageToConversation(activeConversationId, 'bot', text || ''); } catch {}
  if (actions && Array.isArray(actions)) {
    renderActions(actions);
  }
}

function onBizInput() {
  try { localStorage.setItem('x7_business_id', els.businessId.value || ''); } catch {}
}

function getOrCreateSessionId() {
  const key = 'x7_chat_session_id';
  // Use sessionStorage to make the session ephemeral per tab
  let id = null;
  try { id = sessionStorage.getItem(key); } catch {}
  if (!id) {
    const hasCrypto = (typeof crypto !== 'undefined') && crypto && typeof crypto.randomUUID === 'function';
    id = hasCrypto ? crypto.randomUUID() : uuidv4();
    try { sessionStorage.setItem(key, id); } catch {}
  }
  return id;
}

function deriveDedicatedSessionId(baseId, bizId) {
  const suffix = `-biz-${String(bizId).slice(0, 12)}`;
  const id = `${baseId}${suffix}`;
  // Message.session_id max length is 50
  return id.length > 50 ? id.slice(0, 50) : id;
}

// Start a brand-new chat session (ephemeral per tab)
function newChat() {
  // Create a new conversation preserving current mode
  const conv = createConversation({
    isDedicated: !!isDedicated,
    businessId: isDedicated ? activeBusinessId : null,
    title: isDedicated && activeBusinessId ? `Business ${activeBusinessId}` : 'Business Owners Chatting',
  });
  setActiveConversation(conv.id, { connect: true, render: true });
  try { if (els.input) els.input.value = ''; } catch {}
}

function connectWS() {
  cleanupWS();
  const url = new URL(API_BASE);
  const wsScheme = url.protocol === 'https:' ? 'wss' : 'ws';
  const origin = `${wsScheme}://${url.host}`;

  let path;
  const effectiveSessionId = (isDedicated && activeBusinessId)
    ? deriveDedicatedSessionId(sessionId, activeBusinessId)
    : sessionId;
  if (isDedicated && activeBusinessId) {
    path = `/api/v1/dedicated-chat/ws/business/${activeBusinessId}/${effectiveSessionId}`;
  } else {
    // Default to global chat
    path = `/api/v1/global-chat/ws/${effectiveSessionId}`;
  }

  const wsUrl = origin + path;
  ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    setConnStatus(true);
    if (reconnectTimer) { try { clearTimeout(reconnectTimer); } catch {} reconnectTimer = null; }
    reconnectAttempts = 0;
  };
  ws.onclose = () => {
    console.log('WebSocket connection closed');
    setConnStatus(false);
    scheduleReconnect();
  };
  ws.onerror = (err) => {
    console.error('WebSocket error', err);
  };
  ws.onmessage = (evt) => {
    (async () => {
      const raw = typeof evt.data === 'string' ? evt.data : await evt.data.text();
      try {
        const data = JSON.parse(raw);
        console.log('Received WebSocket message:', data.type, data);
        switch (data.type) {
          case 'connected':
            console.log('WebSocket connected message received');
            // Do not render a chat bubble for connection messages
            break;
          case 'typing':
          case 'typing_start':
            // Start typing indicator only if not already typing
            if (!isTyping) {
              isTyping = true;
              // Ensure we have a stream bubble for typing indicator
              ensureStreamBubble();
              console.log('Started typing indicator');
            } else {
              console.log('Ignoring duplicate typing_start message');
            }
            break;
          case 'character':
            // Handle character-by-character streaming
            if (data.character) {
              console.log('Received character:', data.character);
              handleCharStream(data.character);
            }
            break;
          case 'word':
            // Handle word-by-word streaming
            if (data.word !== undefined) {
              console.log('Received word:', data.word);
              handleWordStream(data.word);
            }
            break;
          case 'typing_complete':
            console.log('Received typing_complete message:', data.message);
            // Finalize the message only if we've been streaming characters/words
            // and ensure we don't create duplicate messages
            if ((streamEl || playbackQueue.length > 0) && !streamEl?.parentElement?.classList?.contains('finalized')) {
              console.log('Finalizing assistant message from typing_complete:', data.message);
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
            console.log('Received complete message:', data.message);
            // Create a new message bubble for each message
            cleanupStreamBubble();
            renderBot(data.message || '');
            if (data.suggested_actions && Array.isArray(data.suggested_actions)) {
              renderActions(data.suggested_actions);
            }
            break;
          case 'suggested_actions':
            console.log('Received suggested actions:', data.data);
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
              console.log('Finalizing remaining stream content:', finalText);
              if (finalText.trim()) {
                finalizeAssistantMessage(finalText, [], null);
              }
              cleanupStreamBubble();
            }
            break;
          case 'metadata':
            console.log('Received metadata:', data);
            // no-op in UI for now
            break;
          case 'error':
            console.error('Backend error:', data.message);
            renderSystem('Error: ' + data.message);
            break;
          default:
            console.warn('Unknown message type:', data.type, data);
            if (data.message) {
              console.log('Handling unknown message type with message content');
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

function connectDedicatedWS() {
  // Read business ID from UI
  const raw = (els.businessIdInput && els.businessIdInput.value || '').trim();
  if (!raw) {
    notify('Enter a Business ID to connect to Dedicated Chat');
    return;
  }

  if (!/^\d+$/.test(raw)) {
    notify('Please enter a numeric Business ID to use dedicated WebSocket chat');
    return;
  }

  activeBusinessId = parseInt(raw, 10);
  isDedicated = true;
  try { localStorage.setItem('x7_business_id', String(activeBusinessId)); } catch {}
  // Update active conversation metadata to reflect dedicated mode
  try {
    const list = readConversations();
    const idx = list.findIndex(c => c.id === activeConversationId);
    if (idx >= 0) {
      list[idx].isDedicated = true;
      list[idx].businessId = activeBusinessId;
      list[idx].title = `Business ${activeBusinessId}`;
      writeConversations(list);
      renderChatList();
    }
    if (els.contactTitle) els.contactTitle.textContent = `Business ${activeBusinessId}`;
  } catch {}
  connectWS();
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
        // Do not render chat bubble for API selection
      }
      return;
    }
  }
  console.warn('Could not reach API at ' + API_BASE + '. Set ?api=http://localhost:8000/api/v1 and reload.');
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
    // Route message based on chat mode
    let url = `${API_BASE}/global-chat`;
    const context = { channel: 'web' };
    let effectiveSessionId = sessionId;
    if (isDedicated) {
      if (!activeBusinessId) {
        renderSystem('No Business ID set for dedicated chat. Enter a numeric ID and press Dedicated.');
        return;
      }
      url = `${API_BASE}/dedicated-chat/business/${activeBusinessId}`;
      context.entry_point = 'direct';
      effectiveSessionId = deriveDedicatedSessionId(sessionId, activeBusinessId);
    }
    const body = { message: text, session_id: effectiveSessionId, context };

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

function renderMessage(role, text, markdown = false, skipPersist = false) {
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
  bubble.appendChild(ts);
  els.messages.appendChild(li);
  els.messages.scrollTop = els.messages.scrollHeight;
  // Persist to active conversation (skip system)
  if (!skipPersist && (role === 'user' || role === 'bot') && activeConversationId) {
    addMessageToConversation(activeConversationId, role, text);
  }
}

function setConnStatus(on) {
  const dot = els.statusDot;
  if (!dot) return;
  dot.classList.toggle('on', !!on);
  dot.classList.toggle('off', !on);
  if (on) {
    if (isDedicated) {
      dot.style.background = '#facc15'; // yellow for dedicated
      dot.title = 'Connected (Dedicated)';
    } else {
      dot.style.background = '#22c55e'; // green for global
      dot.title = 'Connected (Global)';
    }
  } else {
    dot.style.background = '#ef4444'; // red for disconnected
    dot.title = 'Disconnected';
  }
}

function notify(msg) {
  renderSystem(msg);
}

// Include JWT bearer token if available for API requests
function authHeaders(extra = {}) {
  const headers = { Accept: 'application/json', ...extra };
  try {
    const auth = (window.X7Auth && typeof X7Auth.getAuth === 'function') ? X7Auth.getAuth() : null;
    const token = auth && auth.token;
    if (token) headers['Authorization'] = `Bearer ${token}`;
  } catch {}
  return headers;
}

async function fetchDashboardOverview() {
  try {
    const res = await fetch(`${API_BASE}/dashboard/overview`, { headers: authHeaders() });
    if (!res.ok) throw new Error('Failed to fetch overview');
    const data = await res.json();
    renderOverviewStats(data.today);
  } catch (e) {
    console.error(e);
  }
}

function renderOverviewStats(stats) {
  const container = els.overviewStats;
  container.innerHTML = '';
  const items = [
    { label: 'Total Orders', value: stats.total_orders },
    { label: 'Total Revenue', value: `$${stats.total_revenue.toFixed(2)}` },
    { label: 'Pending Orders', value: stats.pending_orders },
    { label: 'Completed Orders', value: stats.completed_orders },
    { label: 'Avg Order Value', value: `$${stats.average_order_value.toFixed(2)}` },
  ];
  for (const item of items) {
    const div = document.createElement('div');
    div.className = 'stat-item';
    div.textContent = `${item.label}: ${item.value}`;
    container.appendChild(div);
  }
}

async function fetchActiveConversations() {
  try {
    const res = await fetch(`${API_BASE}/dashboard/conversations?limit=10`, { headers: authHeaders() });
    if (!res.ok) throw new Error('Failed to fetch conversations');
    const data = await res.json();
    renderConversations(data);
  } catch (e) {
    console.error(e);
  }
}

function renderConversations(conversations) {
  const list = els.conversationsList;
  list.innerHTML = '';
  for (const conv of conversations) {
    const li = document.createElement('li');
    li.textContent = `${conv.last_message_time} - ${conv.last_message} (${conv.message_count} msgs)`;
    list.appendChild(li);
  }
}

async function fetchLiveOrders() {
  try {
    const res = await fetch(`${API_BASE}/dashboard/orders/live`, { headers: authHeaders() });
    if (!res.ok) throw new Error('Failed to fetch live orders');
    const data = await res.json();
    renderLiveOrders(data);
  } catch (e) {
    console.error(e);
  }
}

function renderLiveOrders(orders) {
  const list = els.liveOrdersList;
  list.innerHTML = '';
  for (const order of orders) {
    const li = document.createElement('li');
    li.textContent = `Order #${order.id} - Table ${order.table_id} - ${order.status} - $${order.total.toFixed(2)}`;
    list.appendChild(li);
  }
}

// Fallback UUIDv4
function uuidv4() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0, v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}
