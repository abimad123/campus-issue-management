from apps.users.roles import UserRole

from .models import Issue


def visible_issues_for(user):
    queryset = Issue.objects.all()
    if user.role == UserRole.ADMIN:
        return queryset
    if user.role == UserRole.TECHNICAL_STAFF:
        return queryset.filter(assigned_to=user)
    return queryset.filter(reporter=user)
