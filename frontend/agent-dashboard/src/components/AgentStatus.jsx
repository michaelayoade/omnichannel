import { useEffect, useState } from 'react';
import { getAgentProfile, setAgentStatus } from '../api';

const STATUS_CHOICES = ['online', 'offline', 'busy'];

export default function AgentStatus() {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        // Since the viewset returns a list, we get the first item.
        const response = await getAgentProfile();
        setProfile(response.data[0]);
      } catch (err) {
        setError('Failed to fetch agent profile.');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchProfile();
  }, []);

  const handleStatusChange = async (newStatus) => {
    try {
      const response = await setAgentStatus(newStatus);
      setProfile(response.data);
    } catch (err) {
      console.error('Failed to update status:', err);
      // Optionally, show an error to the user.
    }
  };

  if (loading) {
    return <div className="p-4 border-t border-gray-200 text-sm text-gray-600">Loading status...</div>;
  }

  if (error) {
    return <div className="p-4 border-t border-gray-200 text-sm text-red-500">{error}</div>;
  }

  if (!profile) {
    return null; // Don't render if there's no profile
  }

  return (
    <div className="p-4 border-t border-gray-200">
      <h3 className="font-semibold text-lg mb-2">Agent Status</h3>
      <div className="flex items-center mb-4">
        <span className={`h-3 w-3 rounded-full mr-2 ${profile.status === 'online' ? 'bg-green-500' : 'bg-gray-400'}`}></span>
        <p className="capitalize">{profile.user.username} is {profile.status}</p>
      </div>
      <div className="flex justify-around">
        {STATUS_CHOICES.map((status) => (
          <button
            key={status}
            onClick={() => handleStatusChange(status)}
            disabled={profile.status === status}
            className={`px-3 py-1 text-sm font-semibold rounded-full capitalize ${
              profile.status === status
                ? 'bg-blue-500 text-white cursor-not-allowed'
                : 'bg-gray-200 hover:bg-gray-300'
            }`}
          >
            {status}
          </button>
        ))}
      </div>
    </div>
  );
}
