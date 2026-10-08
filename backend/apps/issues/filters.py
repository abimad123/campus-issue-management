import django_filters

from .models import Issue
from django.db.models import Q


class IssueFilter(django_filters.FilterSet):
    created_after = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    created_before = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")
    assigned_team = django_filters.NumberFilter(field_name="assigned_team_id")
    unassigned = django_filters.BooleanFilter(method="filter_unassigned")
    sla_state = django_filters.CharFilter(method="filter_sla_state")

    def filter_unassigned(self, queryset, name, value):
        return queryset.filter(assigned_team__isnull=True) if value else queryset

    def filter_sla_state(self, queryset, name, value):
        if value == "COMPLETED":
            return queryset.filter(status__in=[Issue.Status.RESOLVED, Issue.Status.CLOSED])
        if value == "NOT_CONFIGURED":
            return queryset.filter(sla_policy__isnull=True)
        if value == "ON_TRACK":
            return queryset.filter(sla_policy__isnull=False, response_breached_at__isnull=True, resolution_breached_at__isnull=True).exclude(
                status__in=[Issue.Status.RESOLVED, Issue.Status.CLOSED]
            ).exclude(sla_events__event_type__in=["RESPONSE_WARNING", "RESOLUTION_WARNING"]).distinct()
        if value == "BREACHED":
            return queryset.filter(Q(response_breached_at__isnull=False) | Q(resolution_breached_at__isnull=False))
        if value == "AT_RISK":
            return queryset.filter(sla_events__event_type__in=["RESPONSE_WARNING", "RESOLUTION_WARNING"]).exclude(
                status__in=[Issue.Status.RESOLVED, Issue.Status.CLOSED]
            ).distinct()
        return queryset

    class Meta:
        model = Issue
        fields = {"status": ["exact"], "priority": ["exact"], "category": ["exact"], "location": ["exact"], "reporter": ["exact"]}
