from rest_framework.permissions import BasePermission, SAFE_METHODS

from apps.users.roles import UserRole


NETWORK_READ_ROLES = {
    UserRole.TECHNICIAN,
    UserRole.SUPERVISOR,
    UserRole.IT_MANAGER,
    UserRole.CAMPUS_ADMIN,
    UserRole.SYSTEM_ADMIN,
}
NETWORK_WRITE_ROLES = {UserRole.IT_MANAGER, UserRole.CAMPUS_ADMIN, UserRole.SYSTEM_ADMIN}


class CanReadNetworkOperations(BasePermission):
    message = "Your role does not have access to network operations records."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role in NETWORK_READ_ROLES)


class CanManageNetworkInventory(BasePermission):
    message = "Only IT managers and campus/system administrators can manage network inventory."

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated and request.user.role in NETWORK_READ_ROLES)
        return bool(request.user and request.user.is_authenticated and request.user.role in NETWORK_WRITE_ROLES)
