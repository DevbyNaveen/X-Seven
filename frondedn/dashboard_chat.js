// dashboard_chat.js - Frontend interface for dashboard AI chat

/**
 * DashboardChatInterface - A frontend class to interact with the dashboard AI chat API endpoints
 * and WebSocket for real-time streaming chat responses with business context.
 * 
 * Features:
 * - Initialize a dashboard chat session with business ID
 * - Send chat messages via REST POST
 * - Connect to WebSocket endpoint for real-time streaming chat responses
 * - Send messages over WebSocket
 * - Close WebSocket connection
 * 
 * Example Usage:
 * ```javascript
 * const chat = new DashboardChatInterface(businessId);
 * chat.connectWebSocket();
 * chat.sendMessage('Show me today\'s orders');
 * // Handle incoming messages via onMessage callback
 * chat.onMessage = (message) => console.log('Received:', message);
 * ```
 */

class DashboardChatInterface {
  /**
   * Create a dashboard chat interface instance
   * @param {string} businessId - The ID of the business
   */
  constructor(businessId) {
    this.businessId = businessId;
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
    const key = 'x7_dashboard_chat_session_id';
    let id = localStorage.getItem(key);
    if (!id) {
      id = crypto.randomUUID ? crypto.randomUUID() : this.uuidv4();
      localStorage.setItem(key, id);
    }
    return id;
  }
  
  // Build headers with JWT if available
  buildAuthHeaders(extra = {}) {
    const headers = { 'Accept': 'application/json', ...extra };
    try {
      const auth = (window.X7Auth && typeof X7Auth.getAuth === 'function') ? X7Auth.getAuth() : null;
      let token = auth && auth.token;
      // Fallback to localStorage if X7Auth is unavailable or lacks token
      if (!token) {
        try {
          const raw = localStorage.getItem('x7_auth');
          if (raw) {
            const parsed = JSON.parse(raw);
            if (parsed && parsed.token) token = parsed.token;
          }
        } catch {}
      }
      if (token) headers['Authorization'] = `Bearer ${token}`;
    } catch {}
    return headers;
  }

  /**
   * Send a message to the dashboard chat
   * @param {string} message - The message to send
   * @returns {Promise<Object>} Response from the chat endpoint
   */
  async sendMessage(message) {
    try {
      const response = await x7Fetch(`${this.apiBase}/chat/dashboard`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: message,
          session_id: this.sessionId,
          context: {
            business_id: this.businessId
          }
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
      
      // Create WebSocket URL
      const url = new URL(this.apiBase);
      const wsScheme = url.protocol === 'https:' ? 'wss' : 'ws';
      const origin = `${wsScheme}://${url.host}`;
      
      // Build WebSocket URL
      const wsUrl = `${origin}/api/v1/chat/ws/dashboard/${this.businessId}/${this.sessionId}`;
      
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
          console.log('Connected to dashboard chat WebSocket');
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
        
        case 'word':
          // For word streaming (faster for dashboard users)
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
        
        case 'error':
          console.error('Dashboard chat error:', data.message);
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
   */
  sendWebSocketMessage(message) {
    if (!this.webSocket || !this.isConnected) {
      console.error('WebSocket not connected');
      throw new Error('WebSocket not connected');
    }
    
    const payload = {
      message: message,
      context: {
        business_id: this.businessId
      }
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
  
  // Fallback UUIDv4
  uuidv4() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      const r = Math.random() * 16 | 0, v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
  module.exports = DashboardChatInterface;
} else if (typeof window !== 'undefined') {
  window.DashboardChatInterface = DashboardChatInterface;
}
