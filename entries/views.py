# entries/views.py
from datetime import date
from django.db.models.functions import TruncDate
from django.db.models import Min
from django.contrib.auth import get_user_model
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.conf import settings

from .models import Entry
from .serializers import EntryCreateSerializer, EntryDetailSerializer, EntryListSerializer
from .services import analyze_with_openai
# 개발용 더미: "YYYY-MM-DD": entryId
DUMMY_CALENDAR = {
    "2025-10-01": 101,
    "2025-10-03": 102,
    "2025-10-07": 103,
    "2025-10-11": 104,
    "2025-10-12": 105,
    "2025-10-13": 106,
}


def _get_dev_user():
    """DEBUG일 때 쓰는 가짜 유저를 확보."""
    User = get_user_model()
    # username/email은 원하는 값으로 바꿔도 됩니다.
    user, _ = User.objects.get_or_create(
        username="dev",
        defaults={"email": "dev@example.com"}
    )
    return user

class EntryViewSet(viewsets.ModelViewSet):
    queryset = Entry.objects.all()
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        # DEV에서는 권한 해제
        if settings.DEBUG:
            return [AllowAny()]
        return super().get_permissions()
    
    def get_authenticators(self):
        # DEV에서는 인증 자체 비활성화 → CSRF도 우회
        if settings.DEBUG:
            return []
        return super().get_authenticators()

    def get_queryset(self):
        # 사용자별 필터링: DEV면 dev유저, 운영이면 실제 로그인 유저
        if settings.DEBUG:
            user = _get_dev_user()
        else:
            user = self.request.user
        return Entry.objects.filter(user=user).order_by("-date", "-id")

    def get_serializer_class(self):
        if self.action == "create":
            return EntryCreateSerializer
        if self.action == "list":
            return EntryListSerializer
        return EntryDetailSerializer
    
    def perform_create(self, serializer):
        # 저장 시에도 동일하게 유저 주입
        if settings.DEBUG:
            user = _get_dev_user()
        else:
            user = self.request.user
        serializer.save(user=user)

    def list(self, request, *args, **kwargs):
        """
        - 기본: 사용자의 엔트리 리스트
        - 캘린더 맵: ?calendar=1&month=YYYY-MM
          → { "YYYY-MM-DD": entryId, ... }
        - 개발 더미 사용: &dev_dummy=1 (settings.DEBUG=True 일 때만 동작)
        """
        calendar = request.query_params.get("calendar")
        month = request.query_params.get("month")  # YYYY-MM
        if calendar and month:
            qs = self.get_queryset().filter(date__startswith=month)
            mapping = {e.date.strftime("%Y-%m-%d"): e.id for e in qs}

            # 개발 편의: 더미 합치기 (실서버 X)
            if settings.DEBUG and request.query_params.get("dev_dummy") == "1":
                mapping = {**DUMMY_CALENDAR, **mapping}  # 실제 데이터가 우선되도록 순서 조정 가능

            return Response(mapping)
        return super().list(request, *args, **kwargs)

    @action(detail=False, methods=["GET"], url_path="by-date")
    def by_date(self, request):
        """
        ?date=YYYY-MM-DD → 해당 날짜 엔트리 1개 반환(있으면)
        없으면 404 대신 {"exists": False} 형태로 응답할 수도 있음.
        """
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
        바디: { date, title, original_lang, original_text, meta? }
        - 해당 date에 사용자의 엔트리가 있으면 업데이트
        - 없으면 생성
        → 프론트에서 '특정 날짜 칸 눌러서 작성/수정' UX에 유용
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
@permission_classes([AllowAny])   # 공개(단, 아래에서 DEBUG 체크)
def dev_calendar(request):
    """
    개발 전용: DEBUG=True일 때만 더미 캘린더를 리턴.
    사용: GET /api/dev-calendar/?month=2025-10
    """
    if not settings.DEBUG:
        return Response({"detail": "Not available"}, status=404)

    month = request.query_params.get("month")
    if not month:
        return Response({"detail": "month query param required (YYYY-MM)"}, status=400)

    # DUMMY_CALENDAR는 파일 상단이나 서비스 파일에 정의해 두세요.
    mapping = {k: v for k, v in DUMMY_CALENDAR.items() if k.startswith(f"{month}-")}
    return Response(mapping)

# 오늘의 문장 3개 (프론트 QuoteCarousel 용)
@api_view(["GET"])
@permission_classes([AllowAny])  # 로그인 없이도 가능하게 할지 선택
def quotes(request):
    data = [
        {"en": "Consistency beats perfection.", "ko": "꾸준함은 완벽함을 이깁니다."},
        {"en": "Small steps make big changes.", "ko": "작은 걸음이 큰 변화를 만듭니다."},
        {"en": "Learn something new every day.", "ko": "매일 새로운 것을 배우세요."},
    ]
    return Response(data)
