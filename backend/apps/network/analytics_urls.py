from django.urls import path

from .analytics_views import (
    NetworkAnalyticsBuildingsView,
    NetworkAnalyticsCampusesView,
    NetworkAnalyticsDevicesView,
    NetworkAnalyticsFactorsView,
    NetworkAnalyticsLocationsView,
    NetworkAnalyticsNetworksView,
    NetworkAnalyticsProblemDevicesView,
    NetworkAnalyticsProblemLocationsView,
    NetworkAnalyticsSummaryView,
)
from .trend_views import NetworkTrendsView


urlpatterns = [
    path("network-analytics/trends/", NetworkTrendsView.as_view(), name="network-analytics-trends"),
    path("network-analytics/summary/", NetworkAnalyticsSummaryView.as_view(), name="network-analytics-summary"),
    path("network-analytics/campuses/", NetworkAnalyticsCampusesView.as_view(), name="network-analytics-campuses"),
    path("network-analytics/locations/", NetworkAnalyticsLocationsView.as_view(), name="network-analytics-locations"),
    path("network-analytics/buildings/", NetworkAnalyticsBuildingsView.as_view(), name="network-analytics-buildings"),
    path("network-analytics/devices/", NetworkAnalyticsDevicesView.as_view(), name="network-analytics-devices"),
    path("network-analytics/networks/", NetworkAnalyticsNetworksView.as_view(), name="network-analytics-networks"),
    path("network-analytics/problem-locations/", NetworkAnalyticsProblemLocationsView.as_view(), name="network-analytics-problem-locations"),
    path("network-analytics/problem-devices/", NetworkAnalyticsProblemDevicesView.as_view(), name="network-analytics-problem-devices"),
    path("network-analytics/factors/", NetworkAnalyticsFactorsView.as_view(), name="network-analytics-factors"),
]
