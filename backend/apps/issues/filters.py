import django_filters

from .models import Issue


class IssueFilter(django_filters.FilterSet):
    created_after = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    created_before = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")

    class Meta:
        model = Issue
        fields = {"status": ["exact"], "priority": ["exact"], "category": ["exact"], "location": ["exact"], "reporter": ["exact"]}
