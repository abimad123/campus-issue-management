from rest_framework.authentication import SessionAuthentication


class SPAAuthSessionAuthentication(SessionAuthentication):
    """Session auth with a challenge so anonymous protected API requests return 401."""

    def authenticate_header(self, request):
        return "Session"
