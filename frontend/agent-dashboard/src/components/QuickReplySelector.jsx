import { useState } from 'react';
import { useQuickReplies } from '../hooks/useQuickReplies';
import QuickReplyManager from './QuickReplyManager';

export default function QuickReplySelector({ onSelect }) {
  const { replies, isLoading } = useQuickReplies();
  const [showManager, setShowManager] = useState(false);

  if (isLoading || replies.length === 0) {
    // Don't render anything if loading, error, or no replies
    return null;
  }

  return (
    <div className="p-4 border-t border-gray-200 relative">
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-sm font-semibold text-gray-600">Quick Replies</h4>
        <button onClick={() => setShowManager(true)} className="text-xs text-blue-600">Manage</button>
      </div>
      <div className="flex flex-wrap gap-2">
        {replies.map((reply) => (
          <button
            key={reply.id}
            onClick={() => onSelect(reply.content)}
            className="px-3 py-1 text-sm bg-gray-200 rounded-full hover:bg-gray-300 focus:outline-none"
          >
            {reply.shortcut}
          </button>
        ))}
      </div>
    </div>
  );
}
