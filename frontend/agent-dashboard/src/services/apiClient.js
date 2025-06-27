/**
 * API Client Service
 * Centralized API handling with error management and request/response interceptors
 */
import { useToast } from '../components/ToastContainer';

// Get API base URL from environment variables
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

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
        // Could trigger auth refresh or logout here
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
   * Prepare headers with auth token if available
   */
  getHeaders() {
    const headers = {
      'Content-Type': 'application/json',
    };

    // Add auth token if available
    const token = localStorage.getItem('authToken');
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    return headers;
  }

  /**
   * Make API request with error handling
   */
  async request(endpoint, options = {}) {
    try {
      const url = `${this.baseUrl}${endpoint}`;
      const headers = this.getHeaders();

      const response = await fetch(url, {
        ...options,
        headers: {
          ...headers,
          ...options.headers,
        },
      });

      if (!response.ok) {
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

// Create singleton instance
const apiClient = new ApiClient();

// Hook for using API with toast notifications
export const useApi = () => {
  const toast = useToast();
  apiClient.setToastHandler(toast);
  return apiClient;
};

export default apiClient;
