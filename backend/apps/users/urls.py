from django.urls import path

from .auth_views import CsrfCookieView, CurrentUserView, LoginView, LogoutView

urlpatterns = [
    path("csrf/", CsrfCookieView.as_view(), name="csrf-cookie"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", CurrentUserView.as_view(), name="current-user"),
]
