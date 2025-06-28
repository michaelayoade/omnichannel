import * as Sentry from '@sentry/react';
import { BrowserTracing } from '@sentry/tracing';

/**
 * Initialize Sentry for React application monitoring
 * Uses environment variables for configuration
 */
export const initSentry = () => {
  const dsn = import.meta.env.VITE_SENTRY_DSN;
  const environment = import.meta.env.VITE_ENVIRONMENT || 'development';
  const release = import.meta.env.VITE_APP_VERSION || '1.0.0';
  const tracesSampleRate = parseFloat(import.meta.env.VITE_SENTRY_TRACES_SAMPLE_RATE || '0.2');

  if (dsn) {
    Sentry.init({
      dsn,
      integrations: [new BrowserTracing()],
      environment,
      release: `omnichannel-frontend@${release}`,
      
      // Set tracesSampleRate to 1.0 to capture 100%
      // of transactions for performance monitoring.
      tracesSampleRate,
      
      // Capture user information for better error context
      // The backend should ensure PII is properly handled
      sendDefaultPii: true,
      
      // Only enable in production
      enabled: environment === 'production',
      
      // Handle React router context
      beforeBreadcrumb(breadcrumb) {
        if (breadcrumb.category === 'ui.click') {
          // Enhance click events with better descriptions
          const { target } = breadcrumb;
          if (target && target.innerText) {
            breadcrumb.message = `Button clicked: ${target.innerText.substring(0, 20)}`;
          }
        }
        return breadcrumb;
      }
    });

    // Log successful initialization
    console.log(`Sentry initialized for ${environment} environment`);
  } else {
    console.log('Sentry disabled: No DSN provided');
  }
};

/**
 * Capture exceptions with additional context
 * @param {Error} error - Error object
 * @param {Object} contextData - Additional context about the error
 */
export const captureError = (error, contextData = {}) => {
  if (error) {
    Sentry.withScope((scope) => {
      // Add extra context to the error report
      Object.entries(contextData).forEach(([key, value]) => {
        scope.setExtra(key, value);
      });
      
      Sentry.captureException(error);
    });
  }
};

/**
 * Set user information for better error tracking
 * @param {Object} user - User details object
 */
export const setUserContext = (user) => {
  if (user && user.id) {
    Sentry.setUser({
      id: user.id,
      username: user.username,
      email: user.email,
      role: user.role || 'user'
    });
  } else {
    // Clear user context when logged out
    Sentry.setUser(null);
  }
};

export default {
  init: initSentry,
  captureError,
  setUserContext
};
