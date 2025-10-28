from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EntryViewSet, quotes  # dev_calendar 제거

router = DefaultRouter()
router.register("entries", EntryViewSet, basename="entry")

urlpatterns = [
    path("", include(router.urls)),
    path("quotes/", quotes),
]
