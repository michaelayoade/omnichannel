import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import './index.css';
import './components/toast.css';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import ErrorBoundary from './components/ErrorBoundary';
import { ToastProvider } from './components/ToastContainer';

const queryClient = new QueryClient();

// Function to log errors to backend service when configured
const logErrorToService = (error, errorInfo) => {
  // This could be expanded to send errors to a monitoring service like Sentry
  console.error('Application Error:', error, errorInfo);
};

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary onError={logErrorToService}>
      <ToastProvider>
        <QueryClientProvider client={queryClient}>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </QueryClientProvider>
      </ToastProvider>
    </ErrorBoundary>
  </React.StrictMode>,
);
