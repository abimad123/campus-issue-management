from django.db.models import Count
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.models import User
from apps.users.roles import UserRole


class AdminUserSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != UserRole.ADMIN:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Administrator access is required.")
        counts = {role.value: 0 for role in UserRole}
        counts.update(dict(User.objects.values("role").annotate(total=Count("id")).values_list("role", "total")))
        technicians = User.objects.filter(role=UserRole.TECHNICAL_STAFF).prefetch_related("teams")
        technical_staff = [{
            "id": user.pk,
            "full_name": user.full_name,
            "institutional_id": user.institutional_id,
            "technical_specialization": user.technical_specialization,
            "teams": [team.name for team in user.teams.all()],
            "is_active": user.is_active,
        } for user in technicians]
        return Response({"user_counts": counts, "technical_staff": technical_staff})
