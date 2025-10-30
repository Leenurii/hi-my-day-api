# accounts/views/auth_views.py
import logging

from datetime import datetime, timedelta, timezone
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from accounts.serializers.auth_serializers import TossLoginSerializer, RefreshSerializer
from accounts.integrations.toss_clients import TossMTLS
from accounts.models import AppUser, TossOAuthToken
from accounts.security.app_jwt import issue_app_jwt
logger = logging.getLogger(__name__)

def ts_after(seconds: int):
    return datetime.now(timezone.utc) + timedelta(seconds=seconds)



class TossLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        # 1. 요청 바인딩 & 검증
        ser = TossLoginSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        code = ser.validated_data["authorizationCode"]
        referrer = ser.validated_data.get("referrer")

        client = TossMTLS()

        try:
            #
            # 2. authorizationCode -> 토큰 교환
            #
            token_res = client.generate_token(code, referrer)
            logger.warning(f"[toss-login] token_res = {token_res}")

            if token_res.get("resultType") != "SUCCESS":
                return Response(
                    {
                        "error": "toss_generate_token_failed",
                        "raw": token_res,
                    },
                    status=status.HTTP_502_BAD_GATEWAY,
                )

            token_success = token_res.get("success", {}) or {}

            access_token = token_success.get("accessToken")
            refresh_token = token_success.get("refreshToken")
            access_expires = token_success.get("expiresIn")
            refresh_expires = token_success.get("refreshTokenExpiresIn")  # 가능하면 쓰고, 없으면 None

            if not access_token:
                return Response(
                    {
                        "error": "no_access_token",
                        "raw": token_res,
                    },
                    status=status.HTTP_502_BAD_GATEWAY,
                )

            #
            # 3. access_token -> 유저 정보 조회
            #
            me = client.get_login_me(access_token)
            logger.warning(f"[toss-login] login_me = {me}")

            if me.get("resultType") != "SUCCESS":
                return Response(
                    {
                        "error": "toss_login_me_failed",
                        "raw": me,
                    },
                    status=status.HTTP_502_BAD_GATEWAY,
                )

            me_success = me.get("success", {}) or {}
            toss_user_key = me_success.get("userKey")

            if not toss_user_key:
                return Response(
                    {
                        "error": "no_user_key",
                        "raw": me,
                    },
                    status=status.HTTP_502_BAD_GATEWAY,
                )

            #
            # 4. DB upsert & refresh_token 저장
            #
            with transaction.atomic():
                user, _created = AppUser.objects.get_or_create(
                    toss_user_key=toss_user_key
                )

                if refresh_token:
                    TossOAuthToken.objects.update_or_create(
                        toss_user_key=toss_user_key,
                        defaults={
                            "refresh_token": refresh_token,
                            "refresh_token_expires_at": ts_after(refresh_expires)
                            if refresh_expires
                            else None,
                        },
                    )

            #
            # 5. 우리 앱용 JWT 발급
            #
            app_jwt = issue_app_jwt(
                user.id,
                {"toss_user_key": toss_user_key},
            )

            #
            # 6. 프론트로 최종 응답
            #
            return Response(
                {
                    "jwt": app_jwt,
                    "toss": {
                        "accessTokenExpiresIn": access_expires,
                        "refreshTokenExpiresIn": refresh_expires,
                    },
                    "user": {
                        "id": user.id,
                        "tossUserKey": toss_user_key,
                    },
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.exception("[toss-login] toss_login_failed")
            return Response(
                {
                    "error": "toss_login_failed",
                    "detail": str(e),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

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
