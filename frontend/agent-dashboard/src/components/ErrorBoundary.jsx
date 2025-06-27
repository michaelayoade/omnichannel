import { Component } from 'react';
import PropTypes from 'prop-types';

/**
 * Error Boundary component to catch JavaScript errors in child components
 * and display a fallback UI instead of crashing the whole application
 */
class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null
    };
  }

  static getDerivedStateFromError(error) {
    // Update state so the next render will show the fallback UI
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    // Log the error to an error reporting service
    console.error('Error caught by ErrorBoundary:', error, errorInfo);

    // Store error info for display
    this.setState({ errorInfo });

    // Send to monitoring service if configured
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }
  }

  render() {
    const { hasError, error, errorInfo } = this.state;
    const { fallback, children } = this.props;

    if (hasError) {
      // You can render any custom fallback UI
      if (fallback) {
        return typeof fallback === 'function'
          ? fallback(error, errorInfo)
          : fallback;
      }

      return (
        <div className="error-boundary">
          <div className="error-content">
            <h2>Something went wrong</h2>
            <p>Please try refreshing the page or contact support if the issue persists.</p>
            {process.env.NODE_ENV === 'development' && (
              <details style={{ whiteSpace: 'pre-wrap' }}>
                <summary>Error Details</summary>
                <p>{error && error.toString()}</p>
                <p>{errorInfo && errorInfo.componentStack}</p>
              </details>
            )}
            <button
              className="btn btn-primary mt-3"
              onClick={() => window.location.reload()}
            >
              Refresh Page
            </button>
          </div>
        </div>
      );
    }

    return children;
  }
}

ErrorBoundary.propTypes = {
  children: PropTypes.node.isRequired,
  fallback: PropTypes.oneOfType([PropTypes.node, PropTypes.func]),
  onError: PropTypes.func
};

export default ErrorBoundary;
