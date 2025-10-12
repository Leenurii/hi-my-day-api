from rest_framework.authentication import BaseAuthentication
from rest_framework import exceptions
from django.contrib.auth.models import AnonymousUser
from .app_jwt import verify_app_jwt  
from ..models import AppUser

class AppJWTAuthentication(BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        auth = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth.lower().startswith("bearer "):
            return None
        token = auth.split(" ", 1)[1].strip()
        try:
            payload = verify_app_jwt(token)
            sub = payload.get("sub")
            user = AppUser.objects.filter(id=sub).first()
            if not user:
                raise exceptions.AuthenticationFailed("Invalid user")
            return (user, None)
        except Exception:
            raise exceptions.AuthenticationFailed("Invalid token")
