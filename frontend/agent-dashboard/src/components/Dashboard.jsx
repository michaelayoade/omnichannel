import { useState } from 'react';
import ConversationList from './ConversationList';
import ChatWindow from './ChatWindow';

export default function Dashboard() {
  const [selectedConversationId, setSelectedConversationId] = useState(null);

  return (
    <>
      <ConversationList
        onConversationSelect={setSelectedConversationId}
        selectedConversationId={selectedConversationId}
      />
      <ChatWindow
        selectedConversationId={selectedConversationId}
      />
    </>
  );
}
