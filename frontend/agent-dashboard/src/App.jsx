import { Routes, Route, Link, useLocation } from 'react-router-dom';
import Dashboard from './components/Dashboard';
import AnalyticsDashboard from './components/AnalyticsDashboard';

function App() {
  const location = useLocation();

  const getLinkClass = (path) => {
    return location.pathname === path
      ? 'bg-gray-900 text-white px-3 py-2 rounded-md text-sm font-medium'
      : 'text-gray-300 hover:bg-gray-700 hover:text-white px-3 py-2 rounded-md text-sm font-medium';
  };

  return (
    <div className="flex flex-col h-screen bg-gray-100 font-sans">
      <nav className="bg-gray-800">
        <div className="mx-auto max-w-7xl px-4">
          <div className="relative flex h-16 items-center justify-between">
            <div className="flex flex-1 items-center">
              <div className="flex flex-shrink-0 items-center">
                <p className="text-white font-bold text-lg">Agent Hub</p>
              </div>
              <div className="ml-6">
                <div className="flex space-x-4">
                  <Link to="/" className={getLinkClass('/')}>Dashboard</Link>
                  <Link to="/analytics" className={getLinkClass('/analytics')}>Analytics</Link>
                </div>
              </div>
            </div>
          </div>
        </div>
      </nav>
      <div className="flex flex-1 overflow-hidden">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/analytics" element={<AnalyticsDashboard />} />
        </Routes>
      </div>
    </div>
  );
}

export default App;
