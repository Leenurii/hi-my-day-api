# entries/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EntryViewSet, quotes, dev_calendar

router = DefaultRouter() 
router.register("entries", EntryViewSet, basename="entry")

urlpatterns = [
    path("", include(router.urls)),
    path("quotes/", quotes),
    path("dev-calendar/", dev_calendar),   # ← 개발 전용 공개 엔드포인트

]
