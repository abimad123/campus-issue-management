from rest_framework import viewsets
from apps.audit.services import record_audit
from .models import SlaPolicy
from .serializers import SlaPolicySerializer


class SlaPolicyViewSet(viewsets.ModelViewSet):
    queryset = SlaPolicy.objects.select_related("category").prefetch_related("escalation_levels")
    serializer_class = SlaPolicySerializer

    def get_permissions(self):
        from apps.users.permissions import IsCampusAdministrator
        return [IsCampusAdministrator()]

    def perform_create(self, serializer):
        policy = serializer.save()
        record_audit("sla_policy.created", actor=self.request.user, entity=policy)

    def perform_update(self, serializer):
        policy = serializer.save()
        record_audit("sla_policy.updated", actor=self.request.user, entity=policy)
