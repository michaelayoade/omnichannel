import axios from 'axios';

// Constants for API configuration
const API_CONFIG = {
  BASE_URL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api',
  WS_BASE_URL: (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api')
    .replace('http', 'ws')
    .replace('/api', ''),
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
    const token = localStorage.getItem(API_CONFIG.TOKEN_KEY);
    if (token) {
      config.headers[API_CONFIG.AUTH_HEADER] = `${API_CONFIG.TOKEN_PREFIX} ${token}`;
    }
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
  return apiClient.get('/agent_hub/conversations/');
};

export const getMessages = (conversationId) => {
  return apiClient.get(`/agent_hub/messages/?conversation_id=${conversationId}`);
};

export const connectToConversation = (conversationId, onEvent) => {
  // Input validation
  if (!conversationId) {
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
    const wsUrl = `${API_CONFIG.WS_BASE_URL}/ws/conversations/${conversationId}/?token=${token}`;
    ws = new WebSocket(wsUrl);
  } catch (error) {
    console.error('WebSocket connection error:', error);
    return { close: () => {} };
  }

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
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
