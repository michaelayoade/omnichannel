import React, { useEffect, useState } from 'react';
import { useToast } from '../context/ToastContext';

/**
 * Component that listens for service worker updates and shows a notification
 * allowing the user to refresh for the latest version
 */
function UpdateNotification() {
  const [updateAvailable, setUpdateAvailable] = useState(false);
  const [registration, setRegistration] = useState(null);
  const { addToast } = useToast();

  useEffect(() => {
    // Handler for when a new service worker has been installed
    const handleUpdate = (event) => {
      const newWorker = event.detail;
      setRegistration(newWorker);
      setUpdateAvailable(true);
      
      // Show persistent toast with update notification
      addToast({
        id: 'app-update',
        title: 'Update Available',
        message: 'A new version is available. Click to update now.',
        type: 'info',
        duration: 0, // Persistent until clicked
        onClick: () => refreshApp()
      });
    };

    // Listen for our custom event fired when service worker update is available
    window.addEventListener('serviceWorkerUpdateAvailable', handleUpdate);
    
    return () => {
      window.removeEventListener('serviceWorkerUpdateAvailable', handleUpdate);
    };
  }, [addToast]);

  // Function to refresh the app to get the latest version
  const refreshApp = () => {
    if (registration && registration.waiting) {
      // Tell the service worker to skip waiting
      registration.waiting.postMessage({ type: 'SKIP_WAITING' });
    }
    
    // Reload the page to activate the new service worker
    window.location.reload();
  };

  return null; // This component doesn't render anything visually
}

export default UpdateNotification;
