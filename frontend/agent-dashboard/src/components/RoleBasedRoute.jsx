import React from 'react';
import { Navigate } from 'react-router-dom';
import { useRoles } from '../hooks/useRoles';
import LoadingSpinner from './LoadingSpinner';
import PropTypes from 'prop-types';

/**
 * Component to restrict routes based on user roles
 * @param {Object} props - Component props
 * @param {string[]} props.requiredRoles - Array of roles that can access this route
 * @param {React.ReactNode} props.children - Child components to render
 * @param {string} props.redirectTo - Path to redirect to if unauthorized
 * @returns {JSX.Element} The protected route
 */
const RoleBasedRoute = ({ requiredRoles, children, redirectTo = '/unauthorized' }) => {
  const { roles, hasLoaded } = useRoles();

  // Show loading spinner while roles are being fetched
  if (!hasLoaded) {
    return (
      <div className="flex h-screen items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  // Check if user has at least one of the required roles
  const hasRequiredRole = requiredRoles.some(role => roles.includes(role));

  // Redirect if user doesn't have required role
  if (!hasRequiredRole) {
    return <Navigate to={redirectTo} replace />;
  }

  // Render children if authorized
  return children;
};

RoleBasedRoute.propTypes = {
  requiredRoles: PropTypes.arrayOf(PropTypes.string).isRequired,
  children: PropTypes.node.isRequired,
  redirectTo: PropTypes.string
};

export default RoleBasedRoute;
