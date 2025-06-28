import { useEffect, useState, useRef, useCallback } from 'react';
import { getMessages, connectToConversation, sendMessage } from '../api';
import QuickReplySelector from './QuickReplySelector';
import { AiOutlineCheck, AiOutlineDoubleRight } from 'react-icons/ai';
import { BsFillCheckAllCircleFill } from 'react-icons/bs';
import { useToast } from '../context/ToastContext';
import { sanitizeInput } from '../utils/validation';

export default function ChatWindow({ selectedConversationId }) {
  const [messages, setMessages] = useState([]);
  const [customerTyping, setCustomerTyping] = useState(false);
  const [loading, setLoading] = useState(false);
  const [newMessage, setNewMessage] = useState('');
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef(null);
  const wsRef = useRef(null);
  
  // Access toast notifications
  const { showError, showApiError } = useToast();

  useEffect(() => {
    if (!selectedConversationId) {
      setMessages([]);
      // Clear any existing WebSocket connection
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      return;
    }

    const fetchMessages = async () => {
      setLoading(true);
      try {
        const response = await getMessages(selectedConversationId);
        setMessages(response.data || []);
      } catch (err) {
        showApiError(err, 'Failed to fetch messages');
        // Set empty array to avoid rendering issues
        setMessages([]);
      } finally {
        setLoading(false);
      }
    };

    fetchMessages();

    // Create WebSocket connection with error handling
    try {
      const ws = connectToConversation(selectedConversationId, (event) => {
        switch (event.type) {
          case 'message':
            setMessages((prev) => [...prev, event.payload]);
            break;
          case 'typing':
            if (event.from === 'customer') {
              setCustomerTyping(true);
              // Reset after 3 seconds of inactivity
              setTimeout(() => setCustomerTyping(false), 3000);
            }
            break;
          case 'status':
            setMessages((prev) => prev.map((m) => (m.id === event.message_id ? { ...m, status: event.status } : m)));
            break;
          default:
            break;
        }
      });
      
      wsRef.current = ws;
      
      // Clean up function to close WebSocket when component unmounts or conversation changes
      return () => {
        if (wsRef.current) {
          wsRef.current.close();
          wsRef.current = null;
        }
      };
    } catch (error) {
      showError('Connection error: Could not connect to conversation');
      console.error('WebSocket connection error:', error);
    }
  }, [selectedConversationId, showError, showApiError]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleQuickReplySelect = (content) => {
    // Sanitize content from quick replies
    setNewMessage(sanitizeInput(content));
  };

  const handleInputChange = (e) => {
    setNewMessage(e.target.value);
    notifyTyping();
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!newMessage.trim() || !selectedConversationId) return;
    
    const messageContent = sanitizeInput(newMessage.trim());
    setNewMessage('');
    setSending(true);
    
    // Optimistically add message to UI
    const tempId = `temp-${Date.now()}`;
    const tempMessage = {
      id: tempId,
      content: messageContent,
      sender: 'agent',
      timestamp: new Date().toISOString(),
      status: 'sending'
    };
    
    setMessages((prevMessages) => [...prevMessages, tempMessage]);
    
    try {
      await sendMessage(selectedConversationId, messageContent);
      // Update the status of the sent message
      setMessages((prevMessages) => 
        prevMessages.map(msg => 
          msg.id === tempId ? { ...msg, status: 'sent' } : msg
        )
      );
    } catch (err) {
      // Mark message as failed
      setMessages((prevMessages) => 
        prevMessages.map(msg => 
          msg.id === tempId ? { ...msg, status: 'failed' } : msg
        )
      );
      showApiError(err, 'Failed to send message');
    } finally {
      setSending(false);
    }
  };

  if (!selectedConversationId) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-500">
        Select a conversation to start chatting.
      </div>
    );
  }

  if (loading) {
    return <div className="flex-1 flex items-center justify-center">Loading messages...</div>;
  }

  if (error) {
    return <div className="flex-1 flex items-center justify-center text-red-500">{error}</div>;
  }

  return (
    <div className="flex-1 flex flex-col bg-white">
      <div className="p-4 border-b border-gray-200">
        <h2 className="text-xl font-semibold">Conversation #{selectedConversationId}</h2>
      </div>
      <div className="flex-1 p-4 overflow-y-auto bg-gray-50">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.direction === 'outbound' ? 'justify-end' : 'justify-start'} mb-4`}
          >
            <div
              className={`${msg.direction === 'outbound' ? 'bg-blue-500 text-white' : 'bg-gray-200'} rounded-lg py-2 px-4 max-w-md`}
            >
              <p>{msg.body || msg.content}</p>
              {msg.direction === 'outbound' && (
                <span className="ml-2 text-xs align-middle">
                  {msg.status === 'sending' && <AiOutlineDoubleRight className="inline" />}
                  {msg.status === 'sent' && <AiOutlineCheck className="inline" />}
                  {msg.status === 'delivered' && <AiOutlineDoubleRight className="inline" />}
                  {msg.status === 'read' && <BsFillCheckAllCircleFill className="inline text-blue-400" />}
                </span>
              )}
            </div>
          </div>
        ))}
        {customerTyping && (
          <div className="text-gray-500 italic mb-2">Customer is typing…</div>
        )}
        <div ref={messagesEndRef} />
      </div>
      <div className="p-4 border-t border-gray-200">
        <form onSubmit={handleSubmit}>
          <input
            type="text"
            placeholder="Type a message..."
            className="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            value={newMessage}
            onChange={handleInputChange}
            disabled={!selectedConversationId}
          />
        </form>
      </div>
      <QuickReplySelector onSelect={handleQuickReplySelect} />
    </div>
  );
}
