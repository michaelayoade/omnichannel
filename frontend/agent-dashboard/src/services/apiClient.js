/**
 * API Client Service
 * Centralized API handling with error management, request/response interceptors,
 * and automatic token refresh
 */
import { useToast } from '../context/ToastContext';

// Get API base URL from environment variables
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://149.102.135.97:8000/api';

class ApiClient {
  constructor() {
    this.baseUrl = API_BASE_URL;
    this.toast = null;
  }

  /**
   * Set toast handler for error notifications
   */
  setToastHandler(toastHandler) {
    this.toast = toastHandler;
  }

  /**
   * Handle errors consistently across application
   */
  handleError(error) {
    console.error('API Error:', error);

    // Extract error message
    let errorMessage = 'An unexpected error occurred';

    if (error.response) {
      // Server responded with error status
      const { status, data } = error.response;

      if (status === 401 || status === 403) {
        errorMessage = 'Authentication error. Please log in again.';
        // Auth error handling is now in the request method with refresh token logic
      } else if (status === 404) {
        errorMessage = 'Resource not found';
      } else if (status >= 500) {
        errorMessage = 'Server error. Please try again later.';
      } else if (data && data.message) {
        errorMessage = data.message;
      } else if (data && data.detail) {
        errorMessage = data.detail;
      }
    } else if (error.request) {
      // Request made but no response received
      errorMessage = 'Network error. Please check your connection.';
    }

    // Show toast if available
    if (this.toast) {
      this.toast.showError(errorMessage);
    }

    return Promise.reject(error);
  }

  /**
   * Prepare headers for API requests
   */
  getHeaders() {
    // We no longer need Authorization headers with cookie auth
    // as cookies are automatically sent with the request
    return {
      'Content-Type': 'application/json',
    };
  }

  /**
   * Make API request with error handling and automatic token refresh
   */
  async request(endpoint, options = {}, isRefreshAttempt = false) {
    try {
      const url = `${this.baseUrl}${endpoint}`;
      const headers = this.getHeaders();

      const response = await fetch(url, {
        ...options,
        credentials: 'include', // Important: include cookies in requests
        headers: {
          ...headers,
          ...options.headers,
        },
      });

      if (!response.ok) {
        // Handle 401 by attempting token refresh once
        if (response.status === 401 && !isRefreshAttempt) {
          try {
            // Try to refresh the token
            await this.refreshToken();
            
            // Retry the original request after token refresh
            return this.request(endpoint, options, true);
          } catch (refreshError) {
            // If refresh fails, throw original error
            console.error('Token refresh failed:', refreshError);
            
            // Dispatch event that auth failed (for logout)
            const authFailedEvent = new CustomEvent('auth:failed');
            window.dispatchEvent(authFailedEvent);
            
            // Throw original error
            const errorData = await response.json().catch(() => ({}));
            throw { response: { status: response.status, data: errorData } };
          }
        }
        
        const errorData = await response.json().catch(() => ({}));
        throw { response: { status: response.status, data: errorData } };
      }

      // For 204 No Content responses
      if (response.status === 204) {
        return null;
      }

      return await response.json();
    } catch (error) {
      return this.handleError(error);
    }
  }

  // HTTP method helpers
  async get(endpoint, options = {}) {
    return this.request(endpoint, { ...options, method: 'GET' });
  }

  async post(endpoint, data, options = {}) {
    return this.request(endpoint, {
      ...options,
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async put(endpoint, data, options = {}) {
    return this.request(endpoint, {
      ...options,
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async patch(endpoint, data, options = {}) {
    return this.request(endpoint, {
      ...options,
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  async delete(endpoint, options = {}) {
    return this.request(endpoint, {
      ...options,
      method: 'DELETE',
    });
  }
}

// Add refresh token method to ApiClient
ApiClient.prototype.refreshToken = async function() {
  const url = `${this.baseUrl}/auth/token/refresh/`;
  
  const response = await fetch(url, {
    method: 'POST',
    credentials: 'include', // Important: send cookies
    headers: {
      'Content-Type': 'application/json',
    },
  });
  
  if (!response.ok) {
    throw new Error('Token refresh failed');
  }
  
  return await response.json();
};

// Create singleton instance
const apiClient = new ApiClient();

// Hook for using API with toast notifications
export const useApi = () => {
  const toast = useToast();
  apiClient.setToastHandler(toast);
  return apiClient;
};

export default apiClient;
