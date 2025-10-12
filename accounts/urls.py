from django.urls import path
from .views.auth_views import TossLoginView, TossRefreshView, MeView

urlpatterns = [
    path("toss-login", TossLoginView.as_view()),
    path("toss-refresh", TossRefreshView.as_view()),
    path("me", MeView.as_view()),
]
