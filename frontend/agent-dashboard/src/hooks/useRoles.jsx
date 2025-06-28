import { useState, useEffect, useContext, createContext } from 'react';
import { useAuth } from './useAuth';
import apiClient from '../services/apiClient';

// Create a context for user roles
const RoleContext = createContext({
  roles: [],
  isAdmin: false,
  isSupervisor: false,
  isAgent: false,
  hasLoaded: false,
});

/**
 * Provider component for user role information
 * @param {object} props - Component props
 * @returns {JSX.Element} Provider component
 */
export function RoleProvider({ children }) {
  const [roleState, setRoleState] = useState({
    roles: [],
    isAdmin: false,
    isSupervisor: false,
    isAgent: false,
    hasLoaded: false,
  });
  const { isAuthenticated } = useAuth();

  useEffect(() => {
    // Only fetch roles when user is authenticated
    if (isAuthenticated) {
      const fetchRoles = async () => {
        try {
          // Get user profile which includes group information
          const response = await apiClient.get('/api/agent_hub/agent-profiles/me/');
          
          if (response.data && response.data.groups) {
            const roles = response.data.groups;
            
            setRoleState({
              roles,
              isAdmin: roles.includes('Admin'),
              isSupervisor: roles.includes('Supervisor') || roles.includes('Admin'),
              isAgent: roles.includes('Agent') || roles.includes('Supervisor') || roles.includes('Admin'),
              hasLoaded: true,
            });
          }
        } catch (error) {
          console.error('Failed to fetch user roles:', error);
          // Set default roles in case of error - assume basic agent
          setRoleState({
            roles: ['Agent'],
            isAdmin: false,
            isSupervisor: false,
            isAgent: true,
            hasLoaded: true,
          });
        }
      };

      fetchRoles();
    } else {
      // Reset state when not authenticated
      setRoleState({
        roles: [],
        isAdmin: false,
        isSupervisor: false,
        isAgent: false,
        hasLoaded: true,
      });
    }
  }, [isAuthenticated]);

  return (
    <RoleContext.Provider value={roleState}>
      {children}
    </RoleContext.Provider>
  );
}

/**
 * Hook to access user role information
 * @returns {object} Role information
 */
export function useRoles() {
  return useContext(RoleContext);
}

export default useRoles;
