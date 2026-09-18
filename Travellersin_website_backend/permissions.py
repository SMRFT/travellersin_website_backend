from rest_framework import permissions
from pyauth.auth import HasRolePermission
from .models import Admin

def is_admin_user(user):
    if not user or not getattr(user, 'is_authenticated', False) and not isinstance(user, Admin):
        return False
    if isinstance(user, Admin):
        return getattr(user, 'is_active', True)
    return getattr(user, 'is_superadmin', False) or getattr(user, 'is_staff', False)

class PublicReadOnlyOrHasRolePermission(permissions.BasePermission):
    """
    Allows public GET/HEAD/OPTIONS requests (for website visitors browsing catalog),
    while requiring HasRolePermission or Admin authentication for write/mutation requests (POST, PATCH, DELETE).
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        if is_admin_user(request.user):
            return True
        return HasRolePermission().has_permission(request, view)

class PublicCreateOrHasRolePermission(permissions.BasePermission):
    """
    Allows public POST requests (e.g., customer submitting online booking or inquiry),
    while requiring HasRolePermission or Admin authentication for GET, PATCH, DELETE (admin listing / resolving).
    """
    def has_permission(self, request, view):
        if request.method == "POST":
            auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
            if not auth_header:
                return True
        if is_admin_user(request.user):
            return True
        return HasRolePermission().has_permission(request, view)

class PublicOrHasRolePermission(permissions.BasePermission):
    """
    Allows public guest access (e.g. check availability, track booking, cancel booking),
    while validating HasRolePermission or Admin authentication if Authorization header is provided.
    """
    def has_permission(self, request, view):
        auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
        if not auth_header:
            return True
        if is_admin_user(request.user):
            return True
        return HasRolePermission().has_permission(request, view)

class AdminOrHasRolePermission(permissions.BasePermission):
    """
    Restricts access to authenticated Admins or users with valid PyAuth HasRolePermission.
    """
    def has_permission(self, request, view):
        if is_admin_user(request.user):
            return True
        return HasRolePermission().has_permission(request, view)

