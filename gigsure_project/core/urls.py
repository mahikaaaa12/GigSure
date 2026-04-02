from django.urls import path
from . import views

urlpatterns = [
    # ── Page routes ─────────────────────────────────────────────
    path("",          views.home,         name="home"),
    path("login/",    views.home,         name="login"),
    path("dashboard/",views.dashboard,    name="dashboard"),
    path("claim/",    views.claim_page,   name="claim"),
    path("weather/",  views.weather_page, name="weather"),

    # ── API routes ───────────────────────────────────────────────
    path("api/signup/", views.signup,  name="api-signup"),
    path("api/login/",  views.login,   name="api-login"),
    path("api/logout/", views.logout,  name="api-logout"),
    path("api/me/",     views.me,      name="api-me"),
    path("weather-data/", views.weather_api),
]