import { createContext, useContext, useState, useCallback } from 'react';
import PropTypes from 'prop-types';
import ToastNotification from './ToastNotification';

// Create a context for toast notifications
export const ToastContext = createContext(null);

/**
 * Hook to use toast notifications from any component
 */
export const useToast = () => {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
};

/**
 * Toast provider component to manage toast notifications globally
 */
export const ToastProvider = ({ children }) => {
  const [toasts, setToasts] = useState([]);

  // Function to add a new toast notification
  const addToast = useCallback((message, options = {}) => {
    const id = Date.now().toString();
    const toast = {
      id,
      message,
      type: options.type || 'info',
      duration: options.duration !== undefined ? options.duration : 5000,
    };

    setToasts(currentToasts => [...currentToasts, toast]);
    return id;
  }, []);

  // Helper functions for different toast types
  const showInfo = useCallback((message, options) =>
    addToast(message, { ...options, type: 'info' }), [addToast]);

  const showSuccess = useCallback((message, options) =>
    addToast(message, { ...options, type: 'success' }), [addToast]);

  const showWarning = useCallback((message, options) =>
    addToast(message, { ...options, type: 'warning' }), [addToast]);

  const showError = useCallback((message, options) =>
    addToast(message, { ...options, type: 'error' }), [addToast]);

  // Function to remove a toast notification
  const removeToast = useCallback((id) => {
    setToasts(currentToasts => currentToasts.filter(toast => toast.id !== id));
  }, []);

  // Context value
  const contextValue = {
    addToast,
    removeToast,
    showInfo,
    showSuccess,
    showWarning,
    showError,
  };

  return (
    <ToastContext.Provider value={contextValue}>
      {children}
      <div className="toast-container">
        {toasts.map(toast => (
          <ToastNotification
            key={toast.id}
            message={toast.message}
            type={toast.type}
            duration={toast.duration}
            onClose={() => removeToast(toast.id)}
          />
        ))}
      </div>
    </ToastContext.Provider>
  );
};

ToastProvider.propTypes = {
  children: PropTypes.node.isRequired,
};

export default ToastProvider;
