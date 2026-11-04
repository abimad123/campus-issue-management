from rest_framework.permissions import BasePermission, SAFE_METHODS

from apps.users.roles import UserRole


class IssuePermission(BasePermission):
    message = "You do not have access to this issue operation."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        if getattr(view, "action", None) == "create":
            return True
        return user.role in {UserRole.ADMIN, UserRole.TECHNICAL_STAFF}

    def has_object_permission(self, request, view, obj):
        if request.user.role == UserRole.ADMIN:
            return True
        if obj.reporter_id == request.user.id:
            return request.method in SAFE_METHODS
        if request.user.role == UserRole.TECHNICAL_STAFF:
            return obj.assigned_to_id == request.user.id and (
                request.method in SAFE_METHODS or getattr(view, "action", None) == "status"
            )
        return False
