from rest_framework.response import Response
from rest_framework.views import APIView

class HealthView(APIView):
    """Liveness endpoint; it does not imply database readiness."""
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({"status": "ok", "service": "LPU Campus API"})
