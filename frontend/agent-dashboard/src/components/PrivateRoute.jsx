import { Navigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

/**
 * Protect routes by ensuring user is authenticated via cookies.
 * Redirect to /login if user is not authenticated.
 * Shows loading state while checking authentication status.
 */
export default function PrivateRoute({ children }) {
  const { isAuthenticated, isLoading } = useAuth();
  
  // Show loading state while checking auth status
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary"></div>
      </div>
    );
  }
  
  // Redirect to login if not authenticated
  return isAuthenticated ? children : <Navigate to="/login" replace />;
}
