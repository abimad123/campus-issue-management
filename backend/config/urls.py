from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.core.urls")),
    path("api/auth/", include("apps.users.urls")),
    path("api/", include("apps.campus.urls")),
    path("api/", include("apps.assets.urls")),
    path("api/", include("apps.issues.urls")),
    path("api/", include("apps.routing.urls")),
    path("api/", include("apps.sla.urls")),
    path("api/", include("apps.notifications.urls")),
    path("api/", include("apps.workorders.urls")),
    path("api/", include("apps.network.urls")),
    path("api/", include("apps.network.analytics_urls")),
]
