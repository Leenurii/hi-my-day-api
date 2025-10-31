# entries/views.py
from datetime import date
from django.contrib.auth import get_user_model
from django.conf import settings
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
import calendar as py_calendar 
from .models import Entry
from .serializers import EntryCreateSerializer, EntryDetailSerializer, EntryListSerializer
from .services import analyze_with_openai
import json
import random
from pathlib import Path
from rest_framework.exceptions import AuthenticationFailed
from accounts.models import AppUser  # AUTH_USER_MODEL 이 이거라면



def _get_dev_user():
    """DEBUG일 때 쓰는 가짜 유저 (DB에 dev 계정 자동 생성)"""
    User = get_user_model()
    user, _ = User.objects.get_or_create(
        username="dev",
        defaults={"email": "dev@example.com"}
    )
    return user


class EntryViewSet(viewsets.ModelViewSet):
    queryset = Entry.objects.all()
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if settings.DEBUG:
            return [AllowAny()]
        return super().get_permissions()

    def get_authenticators(self):
        if settings.DEBUG:
            return []  # 인증 비활성화 (개발모드)
        return super().get_authenticators()

    def get_queryset(self):
        """DEBUG 모드에서는 dev 유저, 아니면 실제 로그인 유저"""
        user = _get_dev_user() if settings.DEBUG else self.request.user
        return Entry.objects.filter(user=user).order_by("-date", "-id")

    def get_serializer_class(self):
        if self.action == "create":
            return EntryCreateSerializer
        if self.action == "list":
            return EntryListSerializer
        return EntryDetailSerializer

    def perform_create(self, serializer):
        if settings.DEBUG:
            user = _get_dev_user()
        else:
            user = self.request.user
            # 1) 인증 안 된 경우
            if not user or not user.is_authenticated:
                raise AuthenticationFailed("로그인이 필요합니다.")

            # 2) 혹시 Django User로 들어온 경우 AUTH_USER_MODEL로 변환
            # settings.AUTH_USER_MODEL 이 "accounts.AppUser" 라고 가정
            if user.__class__.__name__ != settings.AUTH_USER_MODEL.split(".")[-1]:
                # 예: 토스 JWT 안 탔거나, 다른 인증으로 들어온 경우
                raise AuthenticationFailed("올바른 사용자로 인증되지 않았습니다.")

        serializer.save(user=user)

    def list(self, request, *args, **kwargs):
        calendar_mode = request.query_params.get("calendar")
        month_param = request.query_params.get("month")  # "YYYY-MM"

        if calendar_mode and month_param:
            # month_param 예: "2025-10"
            try:
                year_str, month_str = month_param.split("-")
                year_i = int(year_str)
                month_i = int(month_str)

                # 그 달의 첫째날 / 마지막날 계산
                # monthrange -> (weekday_of_first, number_of_days)
                _weekday, last_day = py_calendar.monthrange(year_i, month_i)

                start_date = date(year_i, month_i, 1)
                end_date = date(year_i, month_i, last_day)

            except Exception:
                return Response(
                    {"detail": "month must be YYYY-MM"},
                    status=400,
                )

            qs = self.get_queryset().filter(date__gte=start_date, date__lte=end_date)
            mapping = {e.date.strftime("%Y-%m-%d"): e.id for e in qs}
            return Response(mapping)

        return super().list(request, *args, **kwargs)

    @action(detail=False, methods=["GET"], url_path="by-date")
    def by_date(self, request):
        """?date=YYYY-MM-DD → 해당 날짜 엔트리 1개 반환"""
        key = request.query_params.get("date")
        if not key:
            return Response({"detail": "date query param required (YYYY-MM-DD)"}, status=400)

        entry = self.get_queryset().filter(date=key).first()
        if not entry:
            return Response({"exists": False}, status=200)

        ser = EntryDetailSerializer(entry)
        return Response({"exists": True, "entry": ser.data})

    @action(detail=False, methods=["POST"], url_path="upsert-by-date")
    def upsert_by_date(self, request):
        """
        { date, title, original_lang, original_text, meta? }
        → 해당 날짜 엔트리 있으면 수정, 없으면 생성
        """
        data = request.data or {}
        key = data.get("date")
        if not key:
            return Response({"detail": "date is required (YYYY-MM-DD)"}, status=400)

        entry = self.get_queryset().filter(date=key).first()
        common = {
            "title": data.get("title", "").strip(),
            "original_lang": data.get("original_lang", "en"),
            "original_text": data.get("original_text", ""),
            "meta": data.get("meta") or {},
        }

        if entry:
            for k, v in common.items():
                setattr(entry, k, v)
            entry.save()
            return Response({"id": entry.id, "action": "updated"}, status=200)
        else:
            ser = EntryCreateSerializer(data={**common, "date": key}, context={"request": request})
            ser.is_valid(raise_exception=True)
            entry = ser.save()
            return Response({"id": entry.id, "action": "created"}, status=201)

    @action(detail=True, methods=["POST"])
    def analyze(self, request, pk=None):
        entry = self.get_object()

        data = analyze_with_openai(
            original_lang=entry.original_lang,
            original_text=entry.original_text,
            title=entry.title,
            meta=entry.meta or {},
        )
        entry.analysis = data
        entry.save(update_fields=["analysis", "updated_at"])

        return Response({"status": "ok", "analysis": data})


@api_view(["GET"])
@permission_classes([AllowAny])
def quotes(request):
    """
    오늘의 한 줄 학습용 문장 3개를 반환.
    en: 영어 표현 (일기에서 바로 쓸 수 있는 톤)
    ko: 한국어 뉘앙스/뜻
    """
    # quotes_data.json 위치 잡기
    # entries/quotes_data.json 기준
    quotes_path = Path(__file__).resolve().parent / "quotes_data.json"

    try:
        with open(quotes_path, "r", encoding="utf-8") as f:
            all_quotes = json.load(f)
    except Exception:
        # 만약 파일이 없거나 깨졌어도 API는 죽지 않게 기본 fallback
        all_quotes = [
            {
                "en": "I'm trying to focus on progress, not perfection.",
                "ko": "완벽보다 조금씩 나아지는 것에 집중하려고 해요."
            },
            {
                "en": "Today felt overwhelming, but I made it through.",
                "ko": "오늘은 버거웠지만 그래도 버텼어요."
            },
            {
                "en": "I’m slowly getting comfortable with being myself.",
                "ko": "조금씩 있는 그대로의 나를 편하게 느끼는 중이에요."
            }
        ]

    # 최소 3개만 주면 되니까, 3개 뽑기
    # all_quotes가 3개 미만이라도 안전하게 처리
    picked = random.sample(all_quotes, k=min(3, len(all_quotes)))

    return Response(picked)