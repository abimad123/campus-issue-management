from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .analytics import AnalyticsQueryError, get_network_analytics
from .permissions import CanReadNetworkOperations


class NetworkAnalyticsView(APIView):
    permission_classes = [IsAuthenticated, CanReadNetworkOperations]
    result_key = None
    groups = ()

    def get(self, request):
        try:
            result = get_network_analytics(request.query_params, include=self.groups)
        except AnalyticsQueryError as error:
            return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)
        if self.result_key is None:
            return Response(result["summary"])

        paginator = PageNumberPagination()
        paginator.page_size = 20
        rows = result["summary"]["primary_factors"] if self.result_key == "primary_factors" else result[self.result_key]
        page = paginator.paginate_queryset(rows, request, view=self)
        response = paginator.get_paginated_response(page)
        response.data["window"] = result["window"]
        return response


class NetworkAnalyticsSummaryView(NetworkAnalyticsView):
    result_key = None
    groups = ()


class NetworkAnalyticsLocationsView(NetworkAnalyticsView):
    result_key = "locations"
    groups = ("locations",)


class NetworkAnalyticsCampusesView(NetworkAnalyticsView):
    result_key = "campuses"
    groups = ("campuses",)


class NetworkAnalyticsBuildingsView(NetworkAnalyticsView):
    result_key = "buildings"
    groups = ("buildings",)


class NetworkAnalyticsDevicesView(NetworkAnalyticsView):
    result_key = "devices"
    groups = ("devices",)


class NetworkAnalyticsNetworksView(NetworkAnalyticsView):
    result_key = "networks"
    groups = ("networks",)


class NetworkAnalyticsProblemLocationsView(NetworkAnalyticsView):
    result_key = "problem_locations"
    groups = ("problem_locations",)


class NetworkAnalyticsProblemDevicesView(NetworkAnalyticsView):
    result_key = "problem_devices"
    groups = ("problem_devices",)


class NetworkAnalyticsFactorsView(NetworkAnalyticsView):
    result_key = "primary_factors"
    groups = ()
