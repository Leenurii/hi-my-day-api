# config/urls.py  (혹은 프로젝트 루트 urls.py)
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from django.views.generic import TemplateView

urlpatterns = [
    path("admin/", admin.site.urls),

    # ✅ entries 라우트 연결
    path("api/", include("entries.urls")),

    path("terms/", TemplateView.as_view(template_name="terms.html"), name="terms"),

]
