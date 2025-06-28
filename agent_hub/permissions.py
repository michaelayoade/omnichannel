"""
Custom permissions for the Agent Hub application.
Implements role-based access control based on user groups.
"""
from rest_framework import permissions


class IsAdmin(permissions.BasePermission):
    """
    Permission to only allow admin group users.
    """

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.groups.filter(name='Admin').exists()
        )


class IsSupervisor(permissions.BasePermission):
    """
    Permission to allow supervisor group users or higher.
    """

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (
                request.user.groups.filter(name='Supervisor').exists()
                or request.user.groups.filter(name='Admin').exists()
            )
        )


class IsAgent(permissions.BasePermission):
    """
    Permission to allow agent group users or higher.
    All authenticated users should be at least in the Agent group.
    """

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (
                request.user.groups.filter(name='Agent').exists()
                or request.user.groups.filter(name='Supervisor').exists()
                or request.user.groups.filter(name='Admin').exists()
            )
        )


class IsAgentOrReadOnly(permissions.BasePermission):
    """
    Permission to allow agents to read any objects
    but only modify their own objects.
    """

    def has_permission(self, request, view):
        # Allow read permissions for any request
        if request.method in permissions.SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)

        # Write permissions only for agents or higher
        return bool(
            request.user
            and request.user.is_authenticated
            and (
                request.user.groups.filter(name='Agent').exists()
                or request.user.groups.filter(name='Supervisor').exists()
                or request.user.groups.filter(name='Admin').exists()
            )
        )

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any authenticated user
        if request.method in permissions.SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)

        # Supervisors and admins can edit any object
        if request.user.groups.filter(name='Supervisor').exists() or request.user.groups.filter(name='Admin').exists():
            return True

        # Agents can only edit their own objects
        return hasattr(obj, 'agent') and obj.agent == request.user


class IsSupervisorOrReadOnly(permissions.BasePermission):
    """
    Permission to allow supervisors to modify objects,
    but agents can only read.
    """

    def has_permission(self, request, view):
        # Allow read permissions for any authenticated request
        if request.method in permissions.SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)

        # Write permissions only for supervisors or higher
        return bool(
            request.user
            and request.user.is_authenticated
            and (
                request.user.groups.filter(name='Supervisor').exists()
                or request.user.groups.filter(name='Admin').exists()
            )
        )
        

class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Permission to allow admins to modify objects,
    but agents and supervisors can only read.
    """

    def has_permission(self, request, view):
        # Allow read permissions for any authenticated request
        if request.method in permissions.SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)

        # Write permissions only for admins
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.groups.filter(name='Admin').exists()
        )
