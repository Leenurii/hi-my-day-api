from rest_framework.authentication import BaseAuthentication
from rest_framework import exceptions
from .app_jwt import verify_app_jwt
from ..models import AppUser


class AppJWTAuthentication(BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        # 1) Authorization 헤더 없으면 패스 (다른 인증 클래스로 넘어가게)
        auth = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth:
            return None

        # 2) Bearer 토큰 형태 아니면 패스
        #    (여기서 바로 에러 내지 말고 None을 반환해야
        #     DRF가 "인증 안 된 요청" 으로 처리해서 401로 깔끔히 나감)
        if not auth.lower().startswith("bearer "):
            return None

        token = auth.split(" ", 1)[1].strip()
        if not token:
            # 토큰이 비어 있으면 인증 실패
            raise exceptions.AuthenticationFailed("Empty token")

        # 3) 토큰 검증
        try:
            payload = verify_app_jwt(token)
        except Exception:
            # 여기서 단순히 Exception 다 잡고 "Invalid token" 으로 보내는 건 OK
            # 이 단계에선 진짜 토큰이 잘못된 거니까
            raise exceptions.AuthenticationFailed("Invalid token")

        # 4) payload 에서 user 식별자 꺼내기
        #    우리가 issue_app_jwt(user.id, {"toss_user_key": ...}) 이렇게 했으니까
        #    sub(=pk) 도 있고, toss_user_key 도 있을 수 있음
        user_id = payload.get("sub") or payload.get("user_id")
        toss_user_key = payload.get("toss_user_key")

        user = None

        # 4-1) 우선 user_id로 찾기
        if user_id:
            user = AppUser.objects.filter(id=user_id).first()

        # 4-2) 없으면 toss_user_key로 찾기
        if not user and toss_user_key:
            user = AppUser.objects.filter(toss_user_key=toss_user_key).first()

        # 4-3) 그래도 없으면 인증 실패
        if not user:
            # 이때는 토큰은 맞았는데 DB에 유저가 없는 케이스
            # 401로 보내면 프런트에서 다시 로그인 유도 가능
            raise exceptions.AuthenticationFailed("User not found")

        # 5) 정상 인증
        return (user, None)
