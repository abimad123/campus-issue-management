from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .analytics import AnalyticsQueryError
from .permissions import CanReadNetworkOperations
from .trends import TrendQueryError, get_network_trends


class NetworkTrendsView(APIView):
    permission_classes = [IsAuthenticated, CanReadNetworkOperations]

    def get(self, request):
        try:
            result = get_network_trends(request.query_params)
        except (AnalyticsQueryError, TrendQueryError) as error:
            return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(result)
