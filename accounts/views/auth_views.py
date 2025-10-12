# accounts/views/auth_views.py
from datetime import datetime, timedelta, timezone
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from accounts.serializers.auth_serializers import TossLoginSerializer, RefreshSerializer
from accounts.integrations.toss_clients import TossMTLS
from accounts.models import AppUser, TossOAuthToken
from accounts.security.app_jwt import issue_app_jwt

def ts_after(seconds: int):
    return datetime.now(timezone.utc) + timedelta(seconds=seconds)

class TossLoginView(APIView):
    permission_classes = [permissions.AllowAny]
    def post(self, request):
        ser = TossLoginSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        code = ser.validated_data["authorizationCode"]
        referrer = ser.validated_data.get("referrer")

        client = TossMTLS()
        try:
            token_res = client.generate_token(code, referrer)
            access_token = token_res.get("accessToken")
            refresh_token = token_res.get("refreshToken")
            access_expires = token_res.get("expiresIn")
            refresh_expires = token_res.get("refreshTokenExpiresIn")

            if not access_token:
                return Response({"error":"no_access_token"}, status=502)

            me = client.get_login_me(access_token)
            toss_user_key = me.get("userKey")
            if not toss_user_key:
                return Response({"error":"no_user_key"}, status=502)

            with transaction.atomic():
                user, _ = AppUser.objects.get_or_create(toss_user_key=toss_user_key)
                if refresh_token:
                    TossOAuthToken.objects.update_or_create(
                        toss_user_key=toss_user_key,
                        defaults={
                            "refresh_token": refresh_token,
                            "refresh_token_expires_at": ts_after(refresh_expires) if refresh_expires else None
                        }
                    )
            app_jwt = issue_app_jwt(user.id, {"toss_user_key": toss_user_key})

            return Response({
                "jwt": app_jwt,
                "toss": {
                    "accessTokenExpiresIn": access_expires,
                    "refreshTokenExpiresIn": refresh_expires,
                },
                "user": {"id": user.id, "tossUserKey": toss_user_key}
            }, status=200)

        except Exception as e:
            return Response({"error":"toss_login_failed","detail":str(e)}, status=502)

class TossRefreshView(APIView):
    permission_classes = [permissions.AllowAny]
    def post(self, request):
        ser = RefreshSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        toss_user_key = ser.validated_data["tossUserKey"]
        rec = TossOAuthToken.objects.filter(toss_user_key=toss_user_key).order_by("-updated_at").first()
        if not rec:
            return Response({"error":"no_refresh_token"}, status=404)

        client = TossMTLS()
        try:
            new_token = client.refresh_token(rec.refresh_token)
            access_token = new_token.get("accessToken")
            expires_in = new_token.get("expiresIn")
            return Response({"accessToken": access_token, "expiresIn": expires_in}, status=200)
        except Exception as e:
            return Response({"error":"refresh_failed","detail":str(e)}, status=502)

class MeView(APIView):
    def get(self, request):
        user = request.user
        return Response({"id": user.id, "tossUserKey": user.toss_user_key}, status=200)
