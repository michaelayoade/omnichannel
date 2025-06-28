import { useState, useEffect, createContext, useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClientInstance from '../services/apiClient';
import { useToast } from '../context/ToastContext';

const AuthContext = createContext();

export function AuthProvider({ children }) {
  const navigate = useNavigate();
  const { showSuccess, showError } = useToast();
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [user, setUser] = useState(null);
  
  // Check authentication status on mount
  useEffect(() => {
    // Try to verify auth status
    checkAuthStatus();
    
    // Listen for auth failed events from apiClient
    const handleAuthFailed = () => {
      logout();
      showError('Your session has expired. Please login again.');
    };
    
    window.addEventListener('auth:failed', handleAuthFailed);
    
    return () => {
      window.removeEventListener('auth:failed', handleAuthFailed);
    };
  }, []);

  // Check if the user is still authenticated 
  const checkAuthStatus = async () => {
    setIsLoading(true);
    try {
      // Call a protected endpoint to verify auth
      const userData = await apiClientInstance.get('/agent_hub/me/');
      setUser(userData);
      setIsAuthenticated(true);
    } catch (error) {
      setIsAuthenticated(false);
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  };

  const login = async (username, password) => {
    try {
      // Login now just returns a cookie, not a token
      await apiClientInstance.post('/auth/token/', { username, password });
      setIsAuthenticated(true);
      setUser({ username }); // Basic user info, should fetch full profile later
      showSuccess('Login successful');
      navigate('/');
    } catch (error) {
      showError('Login failed: ' + (error.response?.data?.detail || 'Please check your credentials'));
      throw error; // Allow the calling component to handle the error
    }
  };

  const logout = async () => {
    // Call logout endpoint to clear cookies on server-side (optional)
    // Or implement on server side later
    
    // Update client state
    setIsAuthenticated(false);
    setUser(null);
    
    // Redirect to login
    navigate('/login');
  };

  return (
    <AuthContext.Provider value={{
      isAuthenticated,
      isLoading,
      user,
      login,
      logout
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
