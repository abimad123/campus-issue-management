from rest_framework.permissions import BasePermission, SAFE_METHODS

from apps.users.roles import UserRole


NETWORK_READ_ROLES = {
    UserRole.TECHNICAL_STAFF,
    UserRole.ADMIN,
}
NETWORK_WRITE_ROLES = {UserRole.ADMIN}


class CanReadNetworkOperations(BasePermission):
    message = "Your role does not have access to network operations records."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.role == UserRole.ADMIN:
            return True
        return user.role == UserRole.TECHNICAL_STAFF and user.technical_specialization.strip().lower() in {"network", "it support"}


class CanManageNetworkInventory(BasePermission):
    message = "Only Admin can manage network inventory."

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return CanReadNetworkOperations().has_permission(request, view)
        return bool(request.user and request.user.is_authenticated and request.user.role in NETWORK_WRITE_ROLES)
