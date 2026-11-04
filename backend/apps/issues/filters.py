import django_filters

from .models import Issue
from django.db.models import Q


class IssueFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method="filter_search", max_length=120)
    created_after = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    created_before = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")
    assigned_team = django_filters.NumberFilter(field_name="assigned_team_id")
    unassigned = django_filters.BooleanFilter(method="filter_unassigned")
    priority_requested = django_filters.BooleanFilter(method="filter_priority_requested")
    automatically_assigned = django_filters.BooleanFilter(method="filter_automatically_assigned")
    sla_state = django_filters.CharFilter(method="filter_sla_state")

    def filter_search(self, queryset, name, value):
        value = value.strip()
        if not value:
            return queryset
        return queryset.filter(
            Q(ticket_number__icontains=value)
            | Q(title__icontains=value)
            | Q(description__icontains=value)
            | Q(location__name__icontains=value)
            | Q(location__building__name__icontains=value)
        ).distinct()

    def filter_unassigned(self, queryset, name, value):
        return queryset.filter(assigned_to__isnull=True) if value else queryset

    def filter_priority_requested(self, queryset, name, value):
        return queryset.filter(priority_requested_at__isnull=not value)

    def filter_automatically_assigned(self, queryset, name, value):
        queryset = queryset.filter(assignments__is_automatic=value)
        return queryset.distinct()

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
