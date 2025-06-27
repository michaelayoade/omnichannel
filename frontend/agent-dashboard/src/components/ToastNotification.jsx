import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';

/**
 * Toast notification component for displaying alerts and messages
 */
const ToastNotification = ({
  message,
  type = 'info',
  duration = 5000,
  onClose
}) => {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    if (duration > 0) {
      const timer = setTimeout(() => {
        setVisible(false);
        if (onClose) setTimeout(onClose, 300); // Allow animation to complete
      }, duration);

      return () => clearTimeout(timer);
    }
  }, [duration, onClose]);

  const handleClose = () => {
    setVisible(false);
    if (onClose) setTimeout(onClose, 300);
  };

  // Determine toast class based on type
  const toastClass = `toast-notification toast-${type} ${visible ? 'visible' : 'hidden'}`;

  // Icon selection based on type
  const getIcon = () => {
    switch (type) {
      case 'success':
        return '✓';
      case 'error':
        return '✕';
      case 'warning':
        return '⚠';
      default:
        return 'ℹ';
    }
  };

  return (
    <div className={toastClass} role="alert">
      <div className="toast-icon">{getIcon()}</div>
      <div className="toast-content">
        <p>{message}</p>
      </div>
      <button className="toast-close" onClick={handleClose} aria-label="Close">
        ✕
      </button>
    </div>
  );
};

ToastNotification.propTypes = {
  message: PropTypes.string.isRequired,
  type: PropTypes.oneOf(['info', 'success', 'warning', 'error']),
  duration: PropTypes.number,
  onClose: PropTypes.func
};

export default ToastNotification;
