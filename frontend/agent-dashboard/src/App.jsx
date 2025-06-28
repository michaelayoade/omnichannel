import { Routes, Route, Link, useLocation } from 'react-router-dom';
import Dashboard from './components/Dashboard';
import { AuthProvider } from './hooks/useAuth';
import PrivateRoute from './components/PrivateRoute';
import RoleBasedRoute from './components/RoleBasedRoute';
import Login from './pages/Login';
import Unauthorized from './pages/Unauthorized';
import AnalyticsDashboard from './components/AnalyticsDashboard';
import UpdateNotification from './components/UpdateNotification';
import NetworkStatus from './components/NetworkStatus';
import { useRoles } from './hooks/useRoles';

function App() {
  const location = useLocation();
  const { isSupervisor, isAdmin, hasLoaded } = useRoles();

  const getLinkClass = (path) => {
    return location.pathname === path
      ? 'bg-gray-900 text-white px-3 py-2 rounded-md text-sm font-medium'
      : 'text-gray-300 hover:bg-gray-700 hover:text-white px-3 py-2 rounded-md text-sm font-medium';
  };

  return (
    <AuthProvider>
      <UpdateNotification />
      <NetworkStatus />
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
                  {/* Only show Analytics to supervisors and admins */}
                  {isSupervisor && (
                    <Link to="/analytics" className={getLinkClass('/analytics')}>Analytics</Link>
                  )}
                  {/* Only show Settings to admins */}
                  {isAdmin && (
                    <Link to="/settings" className={getLinkClass('/settings')}>Settings</Link>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </nav>
      <div className="flex flex-1 overflow-hidden">
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/unauthorized" element={<Unauthorized />} />
          
          {/* Base route available to all authenticated users */}
          <Route path="/" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
          
          {/* Analytics route restricted to supervisors and admins */}
          <Route 
            path="/analytics" 
            element={
              <PrivateRoute>
                <RoleBasedRoute requiredRoles={['Supervisor', 'Admin']}>
                  <AnalyticsDashboard />
                </RoleBasedRoute>
              </PrivateRoute>
            } 
          />
          
          {/* Settings route restricted to admins only */}
          <Route 
            path="/settings" 
            element={
              <PrivateRoute>
                <RoleBasedRoute requiredRoles={['Admin']}>
                  <div className="p-8">
                    <h1 className="text-2xl font-bold mb-4">System Settings</h1>
                    <p>Admin-only settings panel</p>
                  </div>
                </RoleBasedRoute>
              </PrivateRoute>
            } 
          />
        </Routes>
      </div>
    </div>
  </AuthProvider>);
}

export default App;
