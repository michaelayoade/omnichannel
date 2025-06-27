import { useEffect, useState, useRef } from 'react';
import { getMessages, connectToConversation, sendMessage } from '../api';
import QuickReplySelector from './QuickReplySelector';

export default function ChatWindow({ selectedConversationId }) {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [newMessage, setNewMessage] = useState('');
  const messagesEndRef = useRef(null);

  useEffect(() => {
    if (!selectedConversationId) {
      setMessages([]);
      return;
    }

    const fetchMessages = async () => {
      setLoading(true);
      try {
        const response = await getMessages(selectedConversationId);
        setMessages(response.data);
        setError(null);
      } catch (err) {
        setError('Failed to fetch messages.');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchMessages();

    const ws = connectToConversation(selectedConversationId, (newMessage) => {
      setMessages((prevMessages) => [...prevMessages, newMessage]);
    });

    return () => {
      ws.close();
    };
  }, [selectedConversationId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleQuickReplySelect = (content) => {
    setNewMessage(content);
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!newMessage.trim() || !selectedConversationId) return;

    try {
      await sendMessage(selectedConversationId, newMessage);
      setNewMessage('');
    } catch (err) {
      console.error('Failed to send message:', err);
      // Optionally, you can show an error to the user here.
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
              <p>{msg.body}</p>
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>
      <div className="p-4 border-t border-gray-200">
        <form onSubmit={handleSendMessage}>
          <input
            type="text"
            placeholder="Type a message..."
            className="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            disabled={!selectedConversationId}
          />
        </form>
      </div>
      <QuickReplySelector onSelect={handleQuickReplySelect} />
    </div>
  );
}
