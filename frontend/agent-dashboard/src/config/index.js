/**
 * Configuration management for frontend application
 * Centralizes all configurable parameters and provides environment-aware settings
 */

// Default configuration values
const defaultConfig = {
  // API settings
  api: {
    baseUrl: '/api',
    timeout: 30000,
    retryAttempts: 3,
  },

  // Feature flags
  features: {
    enableAnalytics: true,
    enableNotifications: true,
    enableFileAttachments: true,
    enableVoiceNotes: false,
  },

  // UI settings
  ui: {
    theme: 'light',
    dateFormat: 'MMM DD, YYYY',
    timeFormat: 'HH:mm',
    paginationSize: 20,
    maxAttachmentSize: 10485760, // 10MB in bytes
  },

  // Authentication settings
  auth: {
    tokenRefreshInterval: 1000 * 60 * 15, // 15 minutes
    sessionTimeout: 1000 * 60 * 60 * 8, // 8 hours
  },

  // Polling intervals (in milliseconds)
  polling: {
    conversationList: 10000,
    chatMessages: 3000,
    agentStatus: 60000,
  },
};

// Environment-specific overrides
const envSpecificConfig = {
  development: {
    api: {
      baseUrl: import.meta.env.VITE_API_BASE_URL || defaultConfig.api.baseUrl,
    },
    features: {
      enableVoiceNotes: true, // Enable voice notes in development
    },
  },
  test: {
    polling: {
      // Disable polling in test environment
      conversationList: 0,
      chatMessages: 0,
      agentStatus: 0,
    },
  },
  production: {
    api: {
      baseUrl: import.meta.env.VITE_API_BASE_URL || defaultConfig.api.baseUrl,
      retryAttempts: 5, // More retry attempts in production
    },
  },
};

// Determine current environment
const environment = import.meta.env.MODE || 'development';

// Deep merge function for configuration objects
const mergeDeep = (target, source) => {
  const output = {...target};

  if (isObject(target) && isObject(source)) {
    Object.keys(source).forEach(key => {
      if (isObject(source[key])) {
        if (!(key in target)) {
          Object.assign(output, { [key]: source[key] });
        } else {
          output[key] = mergeDeep(target[key], source[key]);
        }
      } else {
        Object.assign(output, { [key]: source[key] });
      }
    });
  }

  return output;
};

// Helper to check if value is an object
const isObject = item => item && typeof item === 'object' && !Array.isArray(item);

// Create the final configuration by merging defaults with environment-specific settings
const config = mergeDeep(defaultConfig, envSpecificConfig[environment] || {});

// Helper for accessing nested config values using dot notation
export const getConfigValue = (path, defaultVal = undefined) => {
  const keys = Array.isArray(path) ? path : path.split('.');
  let result = config;

  for (const key of keys) {
    if (result && Object.prototype.hasOwnProperty.call(result, key)) {
      result = result[key];
    } else {
      return defaultVal;
    }
  }

  return result;
};

export default config;
