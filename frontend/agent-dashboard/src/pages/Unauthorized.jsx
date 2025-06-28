import React from 'react';
import { Link } from 'react-router-dom';
import { useRoles } from '../hooks/useRoles';

/**
 * Unauthorized access page - shown when users try to access pages they don't have permission for
 */
function Unauthorized() {
  const { roles, isAgent } = useRoles();

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100 px-4">
      <div className="w-full max-w-md p-8 space-y-8 bg-white rounded-lg shadow-md">
        <div className="text-center">
          <svg 
            className="mx-auto h-16 w-16 text-yellow-500" 
            fill="none" 
            stroke="currentColor" 
            viewBox="0 0 24 24" 
            xmlns="http://www.w3.org/2000/svg"
          >
            <path 
              strokeLinecap="round" 
              strokeLinejoin="round" 
              strokeWidth="2" 
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
          
          <h1 className="mt-4 text-2xl font-bold text-gray-900">Access Denied</h1>
          
          <p className="mt-2 text-gray-600">
            You don't have permission to access this page.
          </p>
          
          <div className="mt-4 text-sm text-gray-500">
            Your current role{roles.length > 1 ? 's' : ''}: {roles.join(', ') || 'None'}
          </div>
        </div>

        <div className="mt-6">
          <Link
            to="/"
            className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            Return to Dashboard
          </Link>
        </div>

        {isAgent && (
          <p className="mt-4 text-sm text-center text-gray-500">
            If you believe you should have access to this page, 
            please contact your supervisor.
          </p>
        )}
      </div>
    </div>
  );
}

export default Unauthorized;
