from rest_framework.permissions import BasePermission, SAFE_METHODS

from apps.users.roles import ISSUE_MANAGEMENT_ROLES, UserRole


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
        return user.role in ISSUE_MANAGEMENT_ROLES | {UserRole.TECHNICIAN, UserRole.SUPERVISOR}

    def has_object_permission(self, request, view, obj):
        if obj.reporter_id == request.user.id:
            return request.method in SAFE_METHODS
        if request.user.role in ISSUE_MANAGEMENT_ROLES:
            return True
        if request.user.role == UserRole.TECHNICIAN:
            return obj.assigned_to_id == request.user.id and (
                request.method in SAFE_METHODS or getattr(view, "action", None) == "status"
            )
        if request.user.role == UserRole.SUPERVISOR:
            if obj.assigned_team_id is None:
                return request.method in SAFE_METHODS
            return obj.assigned_team_id in request.user.teams.values_list("id", flat=True)
        return False
