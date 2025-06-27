import { useQuery } from '@tanstack/react-query';
import { getConversations } from '../api';
import AgentStatus from './AgentStatus';

export default function ConversationList({ onConversationSelect, selectedConversationId }) {
  const {
    data: conversations,
    isLoading,
    isError,
    error
  } = useQuery({
    queryKey: ['conversations'],
    queryFn: async () => {
      const response = await getConversations();
      return response.data.results;
    },
  });

  if (isLoading) {
    return <div className="w-1/4 border-r border-gray-200 p-4">Loading conversations...</div>;
  }

  if (isError) {
    return <div className="w-1/4 border-r border-gray-200 p-4 text-red-500">Error: {error.message}</div>;
  }

  return (
    <div className="w-1/4 border-r border-gray-200 flex flex-col bg-white">
      <div className="p-4 border-b border-gray-200">
        <h2 className="text-xl font-semibold">Conversations</h2>
      </div>
      <ul className="overflow-y-auto">
        {conversations.length === 0 ? (
          <li className="p-4 text-gray-500">No conversations found.</li>
        ) : (
          conversations.map((conv) => (
            <li
              key={conv.id}
              className={`p-4 border-b border-gray-200 hover:bg-gray-100 cursor-pointer ${
                selectedConversationId === conv.id ? 'bg-gray-200' : ''
              }`}
              onClick={() => onConversationSelect(conv.id)}
            >
              <p className="font-semibold">{conv.customer.name || 'Unknown Customer'}</p>
              <p className="text-sm text-gray-600 truncate">
                Last message placeholder...
              </p>
            </li>
          ))
        )}
      </ul>
      <AgentStatus />
    </div>
  );
}
