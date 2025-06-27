import axios from 'axios';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api',
  withCredentials: true, // Important for sessions/CSRF
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
}, (error) => {
  return Promise.reject(error);
});

export const getConversations = () => {
  return apiClient.get('/agent_hub/conversations/');
};

export const getMessages = (conversationId) => {
  return apiClient.get(`/agent_hub/messages/?conversation_id=${conversationId}`);
};

export const connectToConversation = (conversationId, onMessage) => {
  const token = localStorage.getItem('access_token');
  if (!token) {
    console.error('Authentication token not found. Please log in.');
    // In a real app, you would redirect to a login page.
    return null;
  }

  const wsBaseUrl = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api')
    .replace('http', 'ws')
    .replace('/api', '');
  const ws = new WebSocket(`${wsBaseUrl}/ws/conversations/${conversationId}/?token=${token}`);

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    onMessage(data.message);
  };

  ws.onclose = () => {
    console.warn('WebSocket disconnected');
    // Optionally, you can try to reconnect here.
  };

  return ws;
};

export const sendMessage = (conversationId, messageBody) => {
  return apiClient.post('/agent_hub/messages/', {
    conversation: conversationId,
    body: messageBody,
  });
};

export const getAgentProfile = () => {
  return apiClient.get('/agent_hub/agent-profiles/');
};

export const setAgentStatus = (status) => {
  return apiClient.post('/agent_hub/agent-profiles/set-status/', { status });
};

export const getQuickReplies = () => {
  return apiClient.get('/agent_hub/quick-replies/');
};

export const getPerformanceSnapshots = () => {
  return apiClient.get('/agent_hub/performance-snapshots/');
};
