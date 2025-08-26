// dedicated_chat.js - Frontend interface for dedicated business chat

/**
 * DedicatedChatInterface - A frontend class to interact with the dedicated business chat API endpoints
 * and WebSocket for real-time streaming chat responses with entry point context.
 * 
 * Features:
 * - Initialize a dedicated chat session with business ID, entry point, and optional table ID
 * - Send chat messages via REST POST
 * * - Connect to WebSocket endpoint for real-time streaming chat responses
 * - Send messages over WebSocket
 * - Close WebSocket connection
 * - Fetch business context summary via REST GET
 * 
 * Example Usage:
 * ```javascript
 * const chat = new DedicatedChatInterface('business-123', 'qr_code', 'table-456');
 * chat.connectWebSocket();
 * chat.sendMessage('What are your specials today?');
 * // Handle incoming messages via onMessage callback
 * chat.onMessage = (message) => console.log('Received:', message);
 * ```
 */

class DedicatedChatInterface {
  /**
   * Create a dedicated chat interface instance
   * @param {string} businessId - The ID of the business
   * @param {string} entryPoint - The entry point (e.g., 'direct', 'qr_code', 'link')
   * @param {string} [tableId] - Optional table ID for restaurant context
   */
  constructor(businessId, entryPoint, tableId) {
    this.businessId = businessId;
    this.entryPoint = entryPoint;
    this.tableId = tableId;
    this.sessionId = this.getOrCreateSessionId();
    this.webSocket = null;
    this.isConnected = false;
    
    // API base URL - using the same as app.js
    this.apiBase = (() => {
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
    
    // Callbacks
    this.onMessage = null;
    this.onTypingStart = null;
    this.onTypingEnd = null;
    this.onConnectionChange = null;
  }
  
  /**
   * Get or create a session ID for the chat
   * @returns {string} Session ID
   */
  getOrCreateSessionId() {
    const key = 'x7_dedicated_chat_session_id';
    let id = localStorage.getItem(key);
    if (!id) {
      id = crypto.randomUUID ? crypto.randomUUID() : this.uuidv4();
      localStorage.setItem(key, id);
    }
    return id;
  }
  
  /**
   * Initialize the dedicated chat session
   * @returns {Promise<Object>} Response from the initialization endpoint
   */
  async initializeSession() {
    try {
      const response = await x7Fetch(`${this.apiBase}/dedicated-chat/business/${this.businessId}/initialize`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: this.sessionId,
          entry_point: this.entryPoint,
          table_id: this.tableId,
        }),
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      return await response.json();
    } catch (error) {
      console.error('Error initializing dedicated chat session:', error);
      throw error;
    }
  }
  
  /**
   * Send a message to the dedicated chat
   * @param {string} message - The message to send
   * @param {boolean} stream - Whether to stream the response
   * @returns {Promise<Object>} Response from the chat endpoint
   */
  async sendMessage(message, stream = true) {
    try {
      const response = await x7Fetch(`${this.apiBase}/dedicated-chat/business/${this.businessId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: message,
          session_id: this.sessionId,
          stream: stream,
        }),
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      return await response.json();
    } catch (error) {
      console.error('Error sending message:', error);
      throw error;
    }
  }
  
  /**
   * Connect to the WebSocket endpoint for real-time streaming
   * @returns {Promise<void>}
   */
  async connectWebSocket() {
    if (this.webSocket && this.isConnected) {
      console.log('WebSocket already connected');
      return;
    }
    
    try {
      // Close existing connection if any
      this.closeWebSocket();
      
      // Create WebSocket URL with query parameters
      const url = new URL(this.apiBase);
      const wsScheme = url.protocol === 'https:' ? 'wss' : 'ws';
      const origin = `${wsScheme}://${url.host}`;
      
      // Build WebSocket URL with entry point and table ID as query parameters
      let wsUrl = `${origin}/api/v1/dedicated-chat/ws/business/${this.businessId}/${this.sessionId}`;
      const queryParams = [];
      if (this.entryPoint) queryParams.push(`entry_point=${encodeURIComponent(this.entryPoint)}`);
      if (this.tableId) queryParams.push(`table_id=${encodeURIComponent(this.tableId)}`);
      if (queryParams.length > 0) {
        wsUrl += `?${queryParams.join('&')}`;
      }
      
      console.log('Connecting to WebSocket:', wsUrl);
      
      // Create WebSocket connection
      this.webSocket = new WebSocket(wsUrl);
      
      // Set up event handlers
      this.webSocket.onopen = (event) => {
        console.log('WebSocket connected');
        this.isConnected = true;
        if (this.onConnectionChange) {
          this.onConnectionChange(true);
        }
      };
      
      this.webSocket.onclose = (event) => {
        console.log('WebSocket disconnected');
        this.isConnected = false;
        if (this.onConnectionChange) {
          this.onConnectionChange(false);
        }
      };
      
      this.webSocket.onerror = (error) => {
        console.error('WebSocket error:', error);
      };
      
      this.webSocket.onmessage = (event) => {
        this.handleWebSocketMessage(event);
      };
      
    } catch (error) {
      console.error('Error connecting to WebSocket:', error);
      throw error;
    }
  }
  
  /**
   * Handle incoming WebSocket messages
   * @param {MessageEvent} event - The WebSocket message event
   */
  handleWebSocketMessage(event) {
    try {
      const data = JSON.parse(event.data);
      console.log('Received WebSocket message:', data);
      
      switch (data.type) {
        case 'connected':
          console.log('Connected to dedicated chat WebSocket');
          break;
        
        case 'typing_start':
          if (this.onTypingStart) {
            this.onTypingStart();
          }
          break;
        
        case 'typing_end':
          if (this.onTypingEnd) {
            this.onTypingEnd();
          }
          break;
        
        case 'character':
          // For character streaming, we might want to buffer and send words
          if (this.onMessage) {
            this.onMessage({ type: 'character', data: data.character });
          }
          break;
        
        case 'word':
          // For word streaming
          if (this.onMessage) {
            this.onMessage({ type: 'word', data: data.word });
          }
          break;
        
        case 'typing_complete':
          // Final message
          if (this.onMessage) {
            this.onMessage({ 
              type: 'message', 
              data: data.message || data.partial_message,
              actions: data.suggested_actions
            });
          }
          break;
        
        case 'message':
          // Complete message
          if (this.onMessage) {
            this.onMessage({ 
              type: 'message', 
              data: data.message,
              actions: data.suggested_actions
            });
          }
          break;
        
        case 'suggested_actions':
          if (this.onMessage) {
            this.onMessage({ 
              type: 'actions', 
              data: data.data
            });
          }
          break;
        
        case 'error':
          console.error('Dedicated chat error:', data.message);
          if (this.onMessage) {
            this.onMessage({ 
              type: 'error', 
              data: data.message 
            });
          }
          break;
        
        default:
          console.warn('Unknown message type:', data.type);
          if (this.onMessage) {
            this.onMessage({ 
              type: 'unknown', 
              data: data 
            });
          }
          break;
      }
    } catch (error) {
      // Non-JSON message
      console.log('Received raw WebSocket message:', event.data);
      if (this.onMessage) {
        this.onMessage({ type: 'raw', data: event.data });
      }
    }
  }
  
  /**
   * Send a message over WebSocket
   * @param {string} message - The message to send
   * @param {boolean} stream - Whether to stream the response
   */
  sendWebSocketMessage(message, stream = true) {
    if (!this.webSocket || !this.isConnected) {
      console.error('WebSocket not connected');
      throw new Error('WebSocket not connected');
    }
    
    const payload = {
      message: message,
      stream: stream
    };
    
    this.webSocket.send(JSON.stringify(payload));
  }
  
  /**
   * Close the WebSocket connection
   */
  closeWebSocket() {
    if (this.webSocket) {
      try {
        this.webSocket.close();
      } catch (error) {
        console.error('Error closing WebSocket:', error);
      }
      this.webSocket = null;
      this.isConnected = false;
      if (this.onConnectionChange) {
        this.onConnectionChange(false);
      }
    }
  }
  
  /**
   * Fetch business context summary
   * @returns {Promise<Object>} Business context data
   */
  async fetchBusinessContext() {
    try {
      const response = await x7Fetch(`${this.apiBase}/dedicated-chat/business/${this.businessId}/context?session_id=${encodeURIComponent(this.sessionId)}`);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      return await response.json();
    } catch (error) {
      console.error('Error fetching business context:', error);
      throw error;
    }
  }
  
  // Fallback UUIDv4
  uuidv4() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      const r = Math.random() * 16 | 0, v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  }
}

// Dedicated chat initialization function for the HTML page
async function initDedicatedChat(businessId, entryPoint, tableId) {
  // Validate required parameters
  if (!businessId) {
    console.error('Business ID is required');
    renderSystem('Error: Business ID is required');
    return;
  }
  
  // Set default entry point if not provided
  if (!entryPoint) {
    entryPoint = 'direct';
  }
  
  // Update UI with business info
  document.getElementById('businessName').textContent = `Business ${businessId}`;
  document.getElementById('entryPointInfo').textContent = `Accessed via ${entryPoint.replace('_', ' ')}`;
  
  if (tableId) {
    document.getElementById('tableNumber').textContent = tableId;
    document.getElementById('tableInfo').style.display = 'flex';
  }
  
  // Get references to UI elements
  const els = {
    messages: document.getElementById('messages'),
    input: document.getElementById('input'),
    send: document.getElementById('sendBtn'),
    statusDot: document.getElementById('statusDot'),
    connectBtn: document.getElementById('connectBtn'),
    quickActions: document.getElementById('quickActions')
  };
  
  // Create dedicated chat instance
  const chat = new DedicatedChatInterface(businessId, entryPoint, tableId);
  
  // Streaming state
  let streamBuffer = "";
  let streamEl = null;
  let streamLi = null;
  let playbackQueue = [];
  let playbackTimer = null;
  let playing = false;
  let isTyping = false;
  
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
  
  chat.onConnectionChange = (connected) => {
    setConnStatus(connected);
    if (connected) {
      renderSystem('Connected to business chat');
    } else {
      renderSystem('Disconnected from business chat');
    }
  };
  
  // Streaming helpers
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
  }
  
  function cleanupStreamBubble() {
    if (playbackTimer) { 
      try { clearTimeout(playbackTimer); } catch {} 
      playbackTimer = null; 
    }
    playing = false;
    streamBuffer = '';
    playbackQueue = [];
    if (streamEl || streamLi) {
      try { if (streamLi) streamLi.classList.remove('typing'); } catch {}
      // Remove the temporary typing bubble from the DOM to avoid duplicates
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
    for (let i = 0; i < chunk.length; i++) playbackQueue.push(chunk[i]);
    startPlayback();
  }
  
  function handleWordStream(word) {
    if (word === undefined) return;
    ensureStreamBubble();
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
    const delay = 100 + Math.random() * 50;
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
    const jitter = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min;
    if (ch === '\n') return 230 + jitter(40, 100);
    if (/[\.\!\?]/.test(ch)) return 240 + jitter(80, 160);
    if (/[\,\;\:]/.test(ch)) return 140 + jitter(50, 120);
    if (ch === ' ') return 20 + jitter(10, 40);
    return 34 + jitter(10, 26);
  }
  
  function finalizeAssistantMessage(finalText, actions) {
    cleanupStreamBubble();
    
    // Generate content hash to prevent content duplicates
    const contentHash = getMessageHash(finalText);
    
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
    li.appendChild(ts);
    els.messages.appendChild(li);
    els.messages.scrollTop = els.messages.scrollHeight;
    streamEl = bubble;
    streamLi = li;
    
    if (window.marked && window.DOMPurify) {
      streamEl.innerHTML = DOMPurify.sanitize(marked.parse(finalText || ''));
      try {
        streamEl.querySelectorAll('a').forEach(a => {
          a.setAttribute('target', '_blank');
          a.setAttribute('rel', 'noopener noreferrer');
        });
      } catch {}
    } else {
      streamEl.textContent = finalText || '';
    }
    
    try { if (streamLi) streamLi.classList.remove('typing'); } catch {}
    streamEl = null;
    streamLi = null;
    
    if (actions && Array.isArray(actions)) {
      renderActions(actions);
    }
  }
  
  function renderActions(actions) {
    els.quickActions.innerHTML = '';
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
      els.quickActions.appendChild(btn);
    });
  }
  
  function handleQuickAction(action) {
    const text = action.title;
    renderUser(text);
    if (chat.isConnected) {
      chat.sendWebSocketMessage(text);
    } else {
      // Fallback to REST API
      sendViaRest(text);
    }
  }
  
  async function sendViaRest(text) {
    try {
      const response = await chat.sendMessage(text);
      finalizeAssistantMessage(response.message, response.suggested_actions);
    } catch (error) {
      console.error('Error sending via REST:', error);
      renderSystem('Failed to send message');
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
  
  // Event handlers
  async function connectChat() {
    try {
      // Initialize session
      await chat.initializeSession();
      renderSystem('Chat session initialized');
      
      // Connect to WebSocket
      await chat.connectWebSocket();
    } catch (error) {
      console.error('Error connecting to chat:', error);
      renderSystem('Failed to connect to chat');
    }
  }
  
  async function onSend() {
    const text = els.input.value.trim();
    if (!text) return;
    els.input.value = '';
    renderUser(text);
    
    if (chat.isConnected) {
      chat.sendWebSocketMessage(text);
    } else {
      // Fallback to REST API
      sendViaRest(text);
    }
  }
  
  // Set up event listeners
  els.connectBtn.addEventListener('click', connectChat);
  els.send.addEventListener('click', onSend);
  
  els.input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  });
  
  // Initial connection
  connectChat();
  
  // Initial welcome message
  renderSystem(`Welcome to the dedicated chat for business ${businessId}!`);
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
  module.exports = DedicatedChatInterface;
} else if (typeof window !== 'undefined') {
  window.DedicatedChatInterface = DedicatedChatInterface;
}

/**
 * Example usage:
 * 
 * const chat = new DedicatedChatInterface('business-123', 'qr_code', 'table-456');
 * 
 * // Set up callbacks
 * chat.onMessage = (message) => {
 *   console.log('Received message:', message);
 *   // Handle different message types
 *   if (message.type === 'message') {
 *     // Display complete message
 *     displayMessage(message.data);
 *   } else if (message.type === 'character' || message.type === 'word') {
 *     // Handle streaming
 *     appendToCurrentMessage(message.data);
 *   }
 * };
 * 
 * chat.onConnectionChange = (connected) => {
 *   console.log('Connection status:', connected);
 *   updateConnectionStatus(connected);
 * };
 * 
 * // Initialize and connect
 * await chat.initializeSession();
 * await chat.connectWebSocket();
 * 
 * // Send a message
 * chat.sendWebSocketMessage('Hello, what can you help me with?');
 */
