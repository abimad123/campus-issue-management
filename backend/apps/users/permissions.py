from rest_framework.permissions import BasePermission

from .roles import ADMIN_ROLES


class IsCampusAdministrator(BasePermission):
    message = "Campus administrator access is required."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in ADMIN_ROLES
        )
