// Mock WebSocket server for testing frontend features
import express from 'express';
import { createServer } from 'http';
import { WebSocketServer } from 'ws';
import cors from 'cors';

// Sample data
const quickReplies = [
  { id: 1, shortcut: "Hello", content: "Hello! How can I assist you today?" },
  { id: 2, shortcut: "Thanks", content: "Thank you for contacting us. Is there anything else I can help with?" },
  { id: 3, shortcut: "Goodbye", content: "Thank you for chatting with us today. Have a great day!" }
];

const conversations = [
  { id: 1, customer_name: "John Doe", channel: "web", last_message: "I need help with my order", unread: 2 },
  { id: 2, customer_name: "Jane Smith", channel: "email", last_message: "When will my refund be processed?", unread: 0 }
];

const messages = {
  1: [
    { id: "m1", conversation_id: 1, body: "Hello, I need help with my order #12345", direction: "inbound", timestamp: "2025-06-27T10:00:00Z", status: "read" },
    { id: "m2", conversation_id: 1, body: "I'd be happy to help with your order. Could you provide more details?", direction: "outbound", timestamp: "2025-06-27T10:02:00Z", status: "read" },
    { id: "m3", conversation_id: 1, body: "I ordered a blue shirt but received a red one", direction: "inbound", timestamp: "2025-06-27T10:03:00Z", status: "read" }
  ],
  2: [
    { id: "m4", conversation_id: 2, body: "I requested a refund last week but haven't received it yet", direction: "inbound", timestamp: "2025-06-27T09:00:00Z", status: "read" },
    { id: "m5", conversation_id: 2, body: "Let me check the status of your refund. Could you provide your order number?", direction: "outbound", timestamp: "2025-06-27T09:05:00Z", status: "read" }
  ]
};

// Setup Express
const app = express();
app.use(cors());
app.use(express.json());

// API endpoints
app.get('/agent_hub/quick-replies/', (req, res) => {
  res.json(quickReplies);
});

app.post('/agent_hub/quick-replies/', (req, res) => {
  const newReply = {
    id: Date.now(),
    shortcut: req.body.shortcut,
    content: req.body.content
  };
  quickReplies.push(newReply);
  res.status(201).json(newReply);
});

app.patch('/agent_hub/quick-replies/:id/', (req, res) => {
  const id = parseInt(req.params.id);
  const index = quickReplies.findIndex(r => r.id === id);
  
  if (index === -1) {
    return res.status(404).json({ error: 'Quick reply not found' });
  }
  
  quickReplies[index] = { ...quickReplies[index], ...req.body };
  res.json(quickReplies[index]);
});

app.delete('/agent_hub/quick-replies/:id/', (req, res) => {
  const id = parseInt(req.params.id);
  const index = quickReplies.findIndex(r => r.id === id);
  
  if (index === -1) {
    return res.status(404).json({ error: 'Quick reply not found' });
  }
  
  quickReplies.splice(index, 1);
  res.status(204).send();
});

app.get('/agent_hub/conversations/', (req, res) => {
  res.json(conversations);
});

app.get('/agent_hub/messages/', (req, res) => {
  const conversationId = parseInt(req.query.conversation_id);
  if (!messages[conversationId]) {
    return res.status(404).json({ error: 'Conversation not found' });
  }
  res.json(messages[conversationId]);
});

app.post('/agent_hub/messages/', (req, res) => {
  const { conversation, body } = req.body;
  const conversationId = parseInt(conversation);
  
  if (!messages[conversationId]) {
    return res.status(404).json({ error: 'Conversation not found' });
  }
  
  const newMessage = {
    id: `m${Date.now()}`,
    conversation_id: conversationId,
    body,
    direction: 'outbound',
    timestamp: new Date().toISOString(),
    status: 'sent'
  };
  
  messages[conversationId].push(newMessage);
  
  // Simulate message being delivered after 1 second
  setTimeout(() => {
    const index = messages[conversationId].findIndex(m => m.id === newMessage.id);
    if (index !== -1) {
      messages[conversationId][index].status = 'delivered';
      // Notify all connected clients about status change
      wss.clients.forEach(client => {
        if (client.conversationId === conversationId) {
          client.send(JSON.stringify({
            type: 'status',
            message_id: newMessage.id,
            status: 'delivered'
          }));
        }
      });
    }
  }, 1000);
  
  // Simulate message being read after 3 seconds
  setTimeout(() => {
    const index = messages[conversationId].findIndex(m => m.id === newMessage.id);
    if (index !== -1) {
      messages[conversationId][index].status = 'read';
      // Notify all connected clients about status change
      wss.clients.forEach(client => {
        if (client.conversationId === conversationId) {
          client.send(JSON.stringify({
            type: 'status',
            message_id: newMessage.id,
            status: 'read'
          }));
        }
      });
    }
  }, 3000);
  
  res.status(201).json(newMessage);
});

// Create HTTP server
const server = createServer(app);

// Create WebSocket server
const wss = new WebSocketServer({ server });

wss.on('connection', (ws, req) => {
  const url = new URL(req.url, 'http://localhost:8000');
  const conversationId = parseInt(url.searchParams.get('conversation_id'));
  ws.conversationId = conversationId;
  
  console.log(`WebSocket connected for conversation ${conversationId}`);
  
  // Send initial message
  ws.send(JSON.stringify({
    type: 'connection_established',
    conversation_id: conversationId
  }));
  
  // Simulate customer typing every 10 seconds
  const typingInterval = setInterval(() => {
    ws.send(JSON.stringify({
      type: 'typing',
      from: 'customer',
      conversation_id: conversationId
    }));
    
    // Simulate customer message 2 seconds after typing
    setTimeout(() => {
      const customerMessage = {
        id: `m${Date.now()}`,
        conversation_id: conversationId,
        body: `Customer message at ${new Date().toLocaleTimeString()}`,
        direction: 'inbound',
        timestamp: new Date().toISOString()
      };
      
      if (messages[conversationId]) {
        messages[conversationId].push(customerMessage);
      }
      
      ws.send(JSON.stringify({
        type: 'message',
        payload: customerMessage
      }));
    }, 2000);
  }, 20000);
  
  ws.on('message', (message) => {
    try {
      const data = JSON.parse(message);
      console.log('Received:', data);
      
      // Echo typing events back
      if (data.type === 'typing') {
        // Do nothing, just log
        console.log(`Agent is typing in conversation ${data.conversation_id}`);
      }
    } catch (error) {
      console.error('Error parsing message:', error);
    }
  });
  
  ws.on('close', () => {
    clearInterval(typingInterval);
    console.log(`WebSocket disconnected for conversation ${conversationId}`);
  });
});

// Start server
const PORT = 8000;
server.listen(PORT, () => {
  console.log(`Mock server running on http://localhost:${PORT}`);
  console.log(`WebSocket server running on ws://localhost:${PORT}`);
});
