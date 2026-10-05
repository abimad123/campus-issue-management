from pathlib import Path

from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from .access import visible_issues_for
from .models import IssueAttachment


class IssueAttachmentFileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        attachment = get_object_or_404(
            IssueAttachment.objects.select_related("issue"),
            pk=pk,
            issue__in=visible_issues_for(request.user),
        )
        response = FileResponse(
            attachment.file.open("rb"),
            content_type=attachment.content_type,
            filename=Path(attachment.file.name).name,
        )
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"
        return response
