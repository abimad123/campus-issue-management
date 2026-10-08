from django.db.models import Q
from apps.users.roles import ISSUE_MANAGEMENT_ROLES, UserRole

from .models import Issue


def visible_issues_for(user):
    queryset = Issue.objects.all()
    if user.role in ISSUE_MANAGEMENT_ROLES:
        return queryset
    if user.role == UserRole.TECHNICIAN:
        return queryset.filter(assigned_to=user)
    if user.role == UserRole.SUPERVISOR:
        return queryset.filter(Q(assigned_team__in=user.teams.all()) | Q(assigned_team__isnull=True)).distinct()
    return queryset.filter(reporter=user)
