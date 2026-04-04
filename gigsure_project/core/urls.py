from django.urls import path
from . import views

urlpatterns = [
    # ── Page routes ──────────────────────────────────────────────────
    path("",                views.home,               name="home"),
    path("login/",          views.home,               name="login"),
    path("dashboard/",      views.dashboard,          name="dashboard"),
    path("claim/",          views.claim_page,         name="claim"),
    path("weather/",        views.weather_page,       name="weather"),
    path("insurer/",        views.insurer_dashboard,  name="insurer-dashboard"),
    path("profile/",        views.profile_page,       name="profile"),

    # ── Auth API ─────────────────────────────────────────────────────
    path("api/signup/",     views.signup,             name="api-signup"),
    path("api/login/",      views.login,              name="api-login"),
    path("api/logout/",     views.logout,             name="api-logout"),
    path("api/me/",         views.me,                 name="api-me"),

    # ── Weather API ──────────────────────────────────────────────────
    path("weather-data/",   views.weather_api,        name="weather-data"),

    # ── Claims API ───────────────────────────────────────────────────
    path("api/claims/submit/",              views.submit_claim,  name="api-submit-claim"),
    path("api/claims/mine/",               views.my_claims,     name="api-my-claims"),

    # ── Insurer API ───────────────────────────────────────────────────
    path("api/insurer/claims/",            views.insurer_claims,    name="api-insurer-claims"),
    path("api/insurer/claims/<int:claim_id>/review/",
                                            views.review_claim,      name="api-review-claim"),
    path("api/insurer/analytics/",         views.insurer_analytics, name="api-insurer-analytics"),
    path("api/insurer/monitor/trigger/",   views.trigger_monitor,   name="api-trigger-monitor"),

    # ── Policy CRUD ───────────────────────────────────────────────────
    path("api/policies/",                  views.list_policies,  name="api-list-policies"),
    path("api/policies/create/",           views.create_policy,  name="api-create-policy"),
    path("api/policies/<int:policy_id>/update/", views.update_policy, name="api-update-policy"),
    path("api/policies/<int:policy_id>/delete/", views.delete_policy, name="api-delete-policy"),

    # ── ML & AI APIs ─────────────────────────────────────────────────
    path("api/ml/risk-score/",             views.ml_risk_score,  name="api-ml-risk"),
    path("api/ai/assistant/",              views.ai_assistant,   name="api-ai-assistant"),

    # ── Notifications ─────────────────────────────────────────────────
    path("api/notifications/",             views.my_notifications,       name="api-notifications"),
    path("api/notifications/read/",        views.mark_notifications_read, name="api-notifs-read"),
]