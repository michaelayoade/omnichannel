import { useEffect, useState } from 'react';
import { getQuickReplies } from '../api';

export default function QuickReplySelector({ onSelect }) {
  const [replies, setReplies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchReplies = async () => {
      try {
        const response = await getQuickReplies();
        setReplies(response.data);
      } catch (err) {
        setError('Failed to fetch quick replies.');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchReplies();
  }, []);

  if (loading || error || replies.length === 0) {
    // Don't render anything if loading, error, or no replies
    return null;
  }

  return (
    <div className="p-4 border-t border-gray-200">
      <h4 className="text-sm font-semibold mb-2 text-gray-600">Quick Replies</h4>
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
