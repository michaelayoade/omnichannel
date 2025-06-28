import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import ChatWindow from './ChatWindow';
import { ToastProvider } from '../context/ToastContext';
import * as api from '../api';

// Mock API functions
vi.mock('../api', () => ({
  getMessages: vi.fn(),
  connectToConversation: vi.fn(),
  sendMessage: vi.fn(),
}));

// Test wrapper component with context providers
const renderWithProviders = (ui) => {
  return render(
    <ToastProvider>
      {ui}
    </ToastProvider>
  );
};

describe('ChatWindow Component', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    
    // Default mock implementations
    api.getMessages.mockResolvedValue({ data: [] });
    api.connectToConversation.mockReturnValue({ close: vi.fn() });
    api.sendMessage.mockResolvedValue({ status: 200 });
  });

  test('should not fetch messages when no conversation is selected', async () => {
    renderWithProviders(<ChatWindow selectedConversationId={null} />);
    
    expect(api.getMessages).not.toHaveBeenCalled();
    expect(api.connectToConversation).not.toHaveBeenCalled();
    
    expect(screen.getByText(/Select a conversation/i)).toBeInTheDocument();
  });
  
  test('should fetch messages when conversation is selected', async () => {
    const mockMessages = [
      { id: '1', content: 'Hello', sender: 'user', timestamp: '2025-06-27T10:00:00Z' },
      { id: '2', content: 'Hi there', sender: 'agent', timestamp: '2025-06-27T10:01:00Z' }
    ];
    
    api.getMessages.mockResolvedValue({ data: mockMessages });
    
    renderWithProviders(<ChatWindow selectedConversationId="123" />);
    
    await waitFor(() => {
      expect(api.getMessages).toHaveBeenCalledWith("123");
      expect(api.connectToConversation).toHaveBeenCalledWith("123", expect.any(Function));
    });
    
    expect(await screen.findByText('Hello')).toBeInTheDocument();
    expect(await screen.findByText('Hi there')).toBeInTheDocument();
  });
  
  test('should sanitize and send messages', async () => {
    renderWithProviders(<ChatWindow selectedConversationId="123" />);
    
    const input = screen.getByPlaceholderText(/Type a message/i);
    const form = screen.getByRole('form');
    
    // Input with potentially harmful characters
    fireEvent.change(input, { target: { value: '<script>alert("XSS")</script>' } });
    fireEvent.submit(form);
    
    await waitFor(() => {
      // Check that message was sanitized before sending
      expect(api.sendMessage).toHaveBeenCalledWith(
        "123", 
        expect.not.stringContaining('<script>')
      );
    });
  });
  
  test('should handle API errors when fetching messages', async () => {
    api.getMessages.mockRejectedValue({ 
      userMessage: 'Failed to fetch messages'
    });
    
    renderWithProviders(<ChatWindow selectedConversationId="123" />);
    
    await waitFor(() => {
      expect(api.getMessages).toHaveBeenCalledWith("123");
    });
    
    // Should display empty state rather than crashing
    expect(screen.queryByText(/Loading/i)).not.toBeInTheDocument();
  });
  
  test('should handle websocket connection errors', async () => {
    api.connectToConversation.mockImplementation(() => {
      throw new Error('Connection failed');
    });
    
    renderWithProviders(<ChatWindow selectedConversationId="123" />);
    
    await waitFor(() => {
      expect(api.connectToConversation).toHaveBeenCalledWith("123", expect.any(Function));
    });
    
    // Component should not crash when WebSocket fails
    expect(screen.getByRole('form')).toBeInTheDocument();
  });
});
