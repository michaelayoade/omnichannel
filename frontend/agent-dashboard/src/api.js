import axios from 'axios';

// Constants for API configuration
// Resolve API base URL: prefer environment variable, fallback to relative path
const RAW_API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';

// Derive WebSocket URL from API base URL
const WS_BASE_URL = RAW_API_BASE.startsWith('/')
  ? window.location.origin.replace(/^http/, 'ws')
  : RAW_API_BASE.replace(/^https?/, 'ws').replace(/\/api$/, '');

const API_CONFIG = {
  BASE_URL: RAW_API_BASE,
  WS_BASE_URL,
  TIMEOUT: 30000, // 30 seconds
  TOKEN_KEY: 'access_token',
  AUTH_HEADER: 'Authorization',
  TOKEN_PREFIX: 'Bearer'
};

// Error messages for consistent user feedback
const ERROR_MESSAGES = {
  NETWORK: 'Network connection error. Please check your internet connection.',
  UNAUTHORIZED: 'Your session has expired. Please log in again.',
  SERVER: 'Server error. Our team has been notified.',
  NOT_FOUND: 'The requested resource was not found.',
  BAD_REQUEST: 'Invalid request. Please check your inputs.',
  VALIDATION: 'Please correct the validation errors.',
  DEFAULT: 'An unexpected error occurred.'
};

// Create axios instance with default configuration
const apiClient = axios.create({
  baseURL: API_CONFIG.BASE_URL,
  timeout: API_CONFIG.TIMEOUT,
  withCredentials: true, // Important for sessions/CSRF
});

// Request interceptor for authentication and logging
apiClient.interceptors.request.use(
  (config) => {
    // Get token from secure storage
    const token = localStorage.getItem(API_CONFIG.TOKEN_KEY);
    
    // Only add valid tokens to prevent security issues
    if (token && typeof token === 'string' && token.trim().length > 0) {
      // Sanitize token before adding to headers
      const sanitizedToken = token.trim();
      config.headers[API_CONFIG.AUTH_HEADER] = `${API_CONFIG.TOKEN_PREFIX} ${sanitizedToken}`;
    }
    
    // Set secure headers
    config.headers['X-Content-Type-Options'] = 'nosniff';
    config.headers['X-XSS-Protection'] = '1; mode=block';
    
    return config;
  }, 
  (error) => {
    console.error('Request error:', error);
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    let errorMessage = ERROR_MESSAGES.DEFAULT;
    
    if (error.message === 'Network Error') {
      errorMessage = ERROR_MESSAGES.NETWORK;
    } else if (error.response) {
      switch (error.response.status) {
        case 400:
          errorMessage = ERROR_MESSAGES.BAD_REQUEST;
          break;
        case 401:
          errorMessage = ERROR_MESSAGES.UNAUTHORIZED;
          // Clear invalid tokens
          localStorage.removeItem(API_CONFIG.TOKEN_KEY);
          break;
        case 404:
          errorMessage = ERROR_MESSAGES.NOT_FOUND;
          break;
        case 422:
          errorMessage = ERROR_MESSAGES.VALIDATION;
          break;
        case 500:
          errorMessage = ERROR_MESSAGES.SERVER;
          break;
        default:
          errorMessage = error.response.data?.message || ERROR_MESSAGES.DEFAULT;
      }
    }
    
    // Add user-friendly message to the error for UI display
    return Promise.reject({
      ...error,
      userMessage: errorMessage,
      timestamp: new Date().toISOString()
    });
  }
);

export const getConversations = () => {
  return apiClient.get('/conversations/');
};

export const getMessages = (conversationId) => {
  return apiClient.get(`/messages/?conversation=${conversationId}`);
};

/**
 * Establishes a secure WebSocket connection to a conversation
 * @param {number|string} conversationId - ID of the conversation to connect to
 * @param {Function} onEvent - Callback function for WebSocket events
 * @returns {WebSocket|Object} - WebSocket connection or dummy object with close method
 */
export const connectToConversation = (conversationId, onEvent) => {
  // Input validation
  if (!conversationId || isNaN(Number(conversationId))) {
    console.error('Cannot connect: Invalid conversation ID');
    return { close: () => {} }; // Return dummy object with close method
  }
  
  const token = localStorage.getItem(API_CONFIG.TOKEN_KEY);
  if (!token) {
    console.error('Authentication token not found. Please log in.');
    // In a real app, you would redirect to a login page.
    return { close: () => {} };
  }

  let ws;
  try {
    // Encode parameters to prevent injection attacks
    const safeConversationId = encodeURIComponent(String(conversationId).trim());
    const safeToken = encodeURIComponent(token.trim());
    
    const wsUrl = `${API_CONFIG.WS_BASE_URL}/ws/conversations/${safeConversationId}/?token=${safeToken}`;
    ws = new WebSocket(wsUrl);
  } catch (error) {
    console.error('WebSocket connection error:', error);
    return { close: () => {} };
  }

  ws.onmessage = (event) => {
    try {
      // Safely parse and validate incoming data
      if (typeof event.data !== 'string') {
        console.error('Invalid WebSocket data format');
        return;
      }
      
      const data = JSON.parse(event.data);
      
      // Validate message structure before processing
      if (!data || typeof data !== 'object') {
        console.error('Invalid message format');
        return;
      }
      
      if (onEvent && typeof onEvent === 'function') {
        onEvent(data);
      }
    } catch (error) {
      console.error('Error parsing WebSocket message:', error);
    }
  };

  ws.onclose = (event) => {
    console.warn(`WebSocket disconnected with code: ${event.code}`, event.reason);
    // Implement reconnection logic if needed
  };
  
  ws.onerror = (error) => {
    console.error('WebSocket error:', error);
  };

  return ws;
};

export const sendMessage = (conversationId, messageBody) => {
  // Input validation
  if (!conversationId) {
    return Promise.reject({
      userMessage: 'Invalid conversation ID'
    });
  }
  
  if (!messageBody || messageBody.trim() === '') {
    return Promise.reject({
      userMessage: 'Message cannot be empty'
    });
  }
  
  // Basic sanitization - trim whitespace
  const sanitizedMessage = messageBody.trim();
  
  return apiClient.post('/agent_hub/messages/', {
    conversation: conversationId,
    body: sanitizedMessage,
    timestamp: new Date().toISOString()
  });
};

export const getAgentProfile = () => {
  return apiClient.get('/agent_hub/agent-profiles/');
};

export const setAgentStatus = (status) => {
  return apiClient.post('/agent_hub/agent-profiles/set-status/', { status });
};

export const getQuickReplies = () => apiClient.get('/agent_hub/quick-replies/');

export const createQuickReply = (payload) => apiClient.post('/agent_hub/quick-replies/', payload);

export const updateQuickReply = (id, payload) => apiClient.patch(`/agent_hub/quick-replies/${id}/`, payload);

export const deleteQuickReply = (id) => apiClient.delete(`/agent_hub/quick-replies/${id}/`);

export const getPerformanceSnapshots = () => {
  return apiClient.get('/agent_hub/performance-snapshots/');
};
