import PropTypes from 'prop-types';
import ToastNotification from './ToastNotification';

/**
 * Container for toast notifications that renders all active toasts
 * Works with the ToastContext to display notifications from anywhere in the app
 */
const ToastContainer = ({ toasts, removeToast }) => {
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-md">
      {toasts.map(toast => (
        <ToastNotification
          key={toast.id}
          message={toast.message}
          type={toast.type}
          duration={toast.duration}
          onClose={() => removeToast(toast.id)}
        />
      ))}
    </div>
  );
};

ToastContainer.propTypes = {
  toasts: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
      message: PropTypes.string.isRequired,
      type: PropTypes.oneOf(['info', 'success', 'warning', 'error']),
      duration: PropTypes.number
    })
  ).isRequired,
  removeToast: PropTypes.func.isRequired
};

export default ToastContainer;
