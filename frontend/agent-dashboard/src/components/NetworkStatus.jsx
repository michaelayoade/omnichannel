import React, { useState, useEffect } from 'react';
import { useToast } from '../context/ToastContext';

/**
 * Component that monitors internet connectivity and displays notifications
 * when the connection status changes
 */
function NetworkStatus() {
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const { addToast, removeToast } = useToast();
  const offlineToastId = 'network-offline';

  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true);
      // Remove offline toast if it exists
      removeToast(offlineToastId);
      // Show reconnected toast
      addToast({
        id: 'network-online',
        title: 'Connection Restored',
        message: 'You are back online.',
        type: 'success',
        duration: 5000
      });
    };

    const handleOffline = () => {
      setIsOnline(false);
      // Show persistent offline toast
      addToast({
        id: offlineToastId,
        title: 'You are offline',
        message: 'Check your internet connection. Some features may be limited.',
        type: 'warning',
        duration: 0 // Persistent until connection is restored
      });
    };

    // Add event listeners for online/offline status
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    // Show offline toast if already offline
    if (!isOnline) {
      handleOffline();
    }

    // Remove event listeners on cleanup
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, [addToast, removeToast, isOnline, offlineToastId]);

  // This component doesn't render anything visually
  return null;
}

export default NetworkStatus;
