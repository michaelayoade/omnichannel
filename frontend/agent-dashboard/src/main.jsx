import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import './index.css';
import './components/toast.css';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import ErrorBoundary from './components/ErrorBoundary';
import { ToastProvider } from './context/ToastContext';
import { RoleProvider } from './hooks/useRoles';

// Initialize monitoring
import sentryService from './services/sentryService';

// Initialize Sentry as early as possible
sentryService.init();

// Register service worker for PWA support
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/service-worker.js')
      .then(registration => {
        console.log('Service Worker registered with scope:', registration.scope);
        
        // Check for service worker updates
        registration.addEventListener('updatefound', () => {
          const newWorker = registration.installing;
          
          newWorker.addEventListener('statechange', () => {
            if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
              // New service worker available - show update notification
              window.dispatchEvent(new CustomEvent('serviceWorkerUpdateAvailable', { detail: registration }));
            }
          });
        });
      })
      .catch(error => {
        console.error('Service Worker registration failed:', error);
        sentryService.captureException(error);
      });
  });
}

// Configure React Query with defaults for better error handling
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: (failureCount, error) => {
        // Don't retry on 404s or auth errors
        if (error.response?.status === 404 || error.response?.status === 401) {
          return false;
        }
        // Retry up to 2 times for other errors
        return failureCount < 2;
      },
      staleTime: 1000 * 60 * 5, // 5 minutes
    },
    mutations: {
      retry: false,
      // We'll handle these errors directly in the components with our toast system
    },
  },
});

// Function to log errors to backend service
const logErrorToService = (error, errorInfo) => {
  // This could be expanded to send errors to a monitoring service like Sentry
  console.error('Application Error:', error, errorInfo);
  
  // Log to backend if in production
  if (import.meta.env.PROD) {
    try {
      fetch('/api/error-log', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          error: {
            message: error?.message || 'Unknown error',
            stack: error?.stack,
            name: error?.name
          },
          errorInfo,
          timestamp: new Date().toISOString(),
          userAgent: navigator.userAgent,
        })
      }).catch(err => console.error('Failed to log error:', err));
    } catch (e) {
      console.error('Error logging failed:', e);
    }
  }
};

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ToastProvider>
      <ErrorBoundary onError={logErrorToService}>
        <QueryClientProvider client={queryClient}>
          <BrowserRouter>
            <RoleProvider>
              <App />
            </RoleProvider>
          </BrowserRouter>
        </QueryClientProvider>
      </ErrorBoundary>
    </ToastProvider>
  </React.StrictMode>,
);
