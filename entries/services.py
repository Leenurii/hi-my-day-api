from __future__ import annotations
import os, json
from typing import Any, Dict
from openai import OpenAI, RateLimitError, APIError
from rest_framework.response import Response
from rest_framework import status

client = OpenAI()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_TIMEOUT = int(os.getenv("OPENAI_TIMEOUT", "20"))

# ✅ 시스템 인스트럭션 업데이트
# - score 필드 포함
# - 전체 JSON 스키마를 명확히 못 박음
SYSTEM_INSTRUCTION = (
    "You are an English writing tutor for Korean users.\n"
    "You MUST respond ONLY as valid JSON (no markdown, no explanation outside JSON).\n"
    "JSON shape:\n"
    "{\n"
    '  "translation": { "to": "en" | "ko", "text": string },\n'
    '  "corrections": { "corrected": string, "explanations": string[] },\n'
    '  "vocab_suggestions": [ { "word": string, "meaning_ko": string, "example_en": string } ],\n'
    '  "score": { "value": number, "comment_ko": string, "focus_next_time": string }\n'
    "}\n"
    "Rules:\n"
    "- All Korean explanations must be natural and concise.\n"
    "- score.value MUST be an integer from 0 to 100.\n"
    "- Do not add extra keys.\n"
)

def build_prompt(
    original_lang: str,
    original_text: str,
    title: str | None = None,
    meta: dict | None = None
) -> str:
    """
    original_lang: 'en' | 'ko'
    original_text: user's diary body
    title: optional diary title
    meta: things like mood/weather
    """

    meta_line = f"메타데이터: {json.dumps(meta or {}, ensure_ascii=False)}"
    title_line = f"제목: {title or '(없음)'}"

    # ✅ 언어별로 behavior를 갈라서, 모델이 헷갈리지 않게 한다.
    if original_lang == "en":
        lang_note = "원문 언어: 영어"

        # 영어로 쓴 일기인 경우:
        # - translation => 한국어 의역
        # - corrections => 더 자연스러운 영어 + 한국어 설명
        # - vocab_suggestions => 이 상황에서 써볼만한 추가 표현
        # - score => 0~100 / 한국어 피드백
        behavior = (
            "1. translation:\n"
            '   - Set \"to\" to \"ko\".\n'
            "   - \"text\": 위 영어 일기의 전체 의미를 한국어로 자연스럽게 설명식으로 풀어쓴 문장.\n"
            "     (직역 금지. 필자의 감정/상황/의도까지 살려서 한국어로 말해줄 것.)\n\n"

            "2. corrections:\n"
            "   - \"corrected\": 원문 영어를 더 자연스럽고 정확하게 고친 영어 버전.\n"
            "   - \"explanations\": 왜 그렇게 바꿨는지 한국어로 짧게 bullet 형식 설명.\n"
            "     한국어로 답하고, 너무 길게 쓰지 말 것.\n\n"

            "3. vocab_suggestions:\n"
            "   - 사용자가 앞으로 비슷한 상황/기분/맥락에서 써볼 만한 자연스러운 영어 표현 3~5개를 제안.\n"
            "   - 원문에 없던 표현도 적극 추천해도 된다.\n"
            "   - 각 아이템은 {\"word\": 표현(단어/구/문장형 가능), \"meaning_ko\": 한국어 의미/뉘앙스, \"example_en\": 그 표현을 실제로 사용하는 짧은 영어 예문}.\n"
            "   - 예문은 일기 톤(1인칭, 감정 묘사)으로 작성.\n\n"

            "4. score:\n"
            "   - \"value\": 0~100 사이 정수. 문법 정확도, 표현 자연스러움, 감정/상황 묘사의 구체성 세 가지를 기준으로 점수화.\n"
            "   - \"comment_ko\": 잘한 점을 한국어로 짧게 칭찬하고 요약해줄 것.\n"
            "   - \"focus_next_time\": 다음 일기에서 한 가지만 더 신경 쓰면 좋은 포인트를 한국어 한 줄로 제시.\n"
        )
    else:
        lang_note = "원문 언어: 한국어"

        # 한국어로 쓴 일기인 경우:
        # - translation => 자연스러운 영어 번역
        # - corrections => 그 번역을 한 단계 더 네이티브스럽게 다듬은 버전 + 이유
        # - vocab_suggestions => 이 상황에서 자주 쓰는 표현 추천
        # - score => 영어로 표현하려고 한 시도까지 평가
        behavior = (
            "1. translation:\n"
            '   - Set \"to\" to \"en\".\n'
            "   - \"text\": 한국어 원문의 자연스러운 영어 번역. 말투는 일기(1인칭) 스타일을 유지.\n"
            "     너무 딱딱한 비즈니스 영어 말고, 내가 실제로 겪은 하루를 얘기하는 느낌으로.\n\n"

            "2. corrections:\n"
            "   - \"corrected\": 위 번역문을 원어민이 다듬은 것처럼 더 자연스럽게 수정한 최종 영어 버전.\n"
            "   - \"explanations\": 주요 수정 포인트를 한국어로 bullet 형태로 짧게 설명.\n\n"

            "3. vocab_suggestions:\n"
            "   - 사용자가 앞으로 비슷한 상황/감정/맥락에서 써볼 만한 자연스러운 영어 표현 3~5개를 제안.\n"
            "   - 꼭 원문에 있던 단어일 필요는 없다.\n"
            "   - 각 아이템은 {\"word\": 표현(단어/구/문장형 가능), \"meaning_ko\": 한국어 의미/뉘앙스, \"example_en\": 그 표현을 실제로 사용하는 짧은 영어 예문}.\n"
            "   - 예문은 일기 말투(내 얘기)로 작성할 것.\n\n"

            "4. score:\n"
            "   - \"value\": 0~100 사이 정수. 영어로 감정을 표현하려는 시도, 구체성, 자연스러움 가능성 등을 기준으로 점수화.\n"
            "   - \"comment_ko\": 한국어로 짧게 칭찬하고, 특히 좋았던 부분을 알려줄 것.\n"
            "   - \"focus_next_time\": 다음에 한 가지만 더 의식하면 좋을 포인트를 한국어 한 줄로.\n"
        )

    # 실제 모델 입력 프롬프트
    return (
        f"{lang_note}\n"
        "아래 규칙에 따라 반드시 지정된 JSON 형태로만 답하세요.\n\n"
        f"{behavior}\n"
        f"{meta_line}\n"
        f"{title_line}\n\n"
        "---\n"
        "원문 시작\n"
        f"{original_text}\n"
        "원문 끝\n\n"
        "JSON만 출력하세요."
    )


def _parse_json(text: str) -> Dict[str, Any]:
    """
    모델이 준 응답 문자열(text)을 JSON으로 파싱.
    혹시 모델이 살짝 삐끗해도 최소한의 형태는 보장해서 돌려준다.
    """
    try:
        data = json.loads(text)
    except Exception:
        # 완전 망한 경우라도 raw는 남겨서 디버깅 가능하게
        data = {"raw": text}

    # 기본 필드들 강제 세팅 (없으면 빈값으로라도)
    data.setdefault("translation", {})
    data.setdefault("corrections", {})
    data.setdefault("vocab_suggestions", [])
    data.setdefault("score", {})

    return data


def analyze_with_openai(
    *,
    original_lang: str,
    original_text: str,
    title: str | None = None,
    meta: dict | None = None
) -> Dict[str, Any]:
    """
    - original_lang: "en" | "ko"
    - original_text: 유저가 쓴 일기 본문
    - title, meta: 부가정보

    리턴: dict (analysis 결과)
    정상일 땐 dict 형태의 분석결과(JSON) 그대로 반환
    에러일 땐 DRF Response 반환 (429, 502 등)
    """

    prompt = build_prompt(
        original_lang=original_lang,
        original_text=original_text,
        title=title,
        meta=meta,
    )

    # 1) Responses API 우선 사용
    try:
        resp = client.responses.create(
            model=OPENAI_MODEL,
            instructions=SYSTEM_INSTRUCTION,
            input=prompt,
            timeout=OPENAI_TIMEOUT,
            response_format={"type": "json_object"},  # 신형 SDK에서 지원되는 구조
            max_output_tokens=800,
        )

        # SDK 응답에서 모델 답변 텍스트 뽑아서 파싱
        return _parse_json(resp.output_text)

    except TypeError:
        # 2) 구버전 SDK 환경이면 chat.completions로 폴백
        chat = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )

        text = chat.choices[0].message.content or ""
        return _parse_json(text)

    except RateLimitError:
        # OpenAI 요청 과금/쿼터 제한 등
        return Response(
            {
                "detail": "OpenAI API 사용 한도를 초과했습니다. Billing 상태를 확인해주세요.",
                "code": "rate_limited",
            },
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    except APIError as e:
        # OpenAI 쪽 장애나 네트워크 이슈 등
        return Response(
            {
                "detail": f"OpenAI API 오류: {getattr(e, 'message', str(e))}",
                "code": "openai_error",
            },
            status=status.HTTP_502_BAD_GATEWAY,
        )
