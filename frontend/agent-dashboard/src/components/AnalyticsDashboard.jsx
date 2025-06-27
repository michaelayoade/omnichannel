import { useEffect, useState } from 'react';
import { getPerformanceSnapshots } from '../api';

// A simple function to format the timedelta string from Django
const formatDuration = (isoDuration) => {
  if (!isoDuration) return 'N/A';
  // Example format: "0 00:05:23.123456" or just "00:05:23.123456"
  const parts = isoDuration.split(' ');
  let timePart = isoDuration;
  if (parts.length > 1) {
    timePart = parts[parts.length - 1];
  }
  const [hours, minutes, seconds] = timePart.split(':');
  return `${parseInt(hours, 10)}h ${parseInt(minutes, 10)}m ${Math.round(parseFloat(seconds))}s`;
};

export default function AnalyticsDashboard() {
  const [snapshots, setSnapshots] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchSnapshots = async () => {
      try {
        const response = await getPerformanceSnapshots();
        setSnapshots(response.data);
      } catch (err) {
        setError('Failed to fetch performance data.');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchSnapshots();
  }, []);

  if (loading) {
    return <div className="p-8 w-full">Loading performance data...</div>;
  }

  if (error) {
    return <div className="p-8 w-full text-red-500">{error}</div>;
  }

  return (
    <div className="p-8 w-full bg-gray-50 flex-1 overflow-y-auto">
      <h1 className="text-3xl font-bold mb-6 text-gray-800">Performance Analytics</h1>
      {snapshots.length === 0 ? (
        <p className="text-gray-600">No performance data available yet. The first snapshot will be generated within an hour.</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {snapshots.map((snapshot) => (
            <div key={snapshot.id} className="bg-white p-6 rounded-lg shadow-md">
              <h3 className="font-semibold text-lg mb-2 text-gray-800">
                {new Date(snapshot.period_start).toLocaleDateString()}
              </h3>
              <div className="space-y-2 text-gray-700">
                <p><strong>Conversations Handled:</strong> {snapshot.conversations_handled}</p>
                <p><strong>Messages Sent:</strong> {snapshot.messages_sent}</p>
                <p><strong>Avg. Resolution Time:</strong> {formatDuration(snapshot.average_resolution_time)}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
