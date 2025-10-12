# entries/services.py
from __future__ import annotations
import os, json
from typing import Any, Dict
from openai import OpenAI, RateLimitError, APIError

client = OpenAI()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_TIMEOUT = int(os.getenv("OPENAI_TIMEOUT", "20"))

SYSTEM_INSTRUCTION = (
    "You are an English writing tutor for Korean users. "
    "Return results ONLY as JSON with the keys: "
    "{translation: {to: 'en'|'ko', text: string}, "
    " corrections: {corrected: string, explanations: string[]}, "
    " vocab_suggestions: [{word: string, meaning_ko: string, example_en: string}] }.\n"
    "Keep explanations concise and helpful in Korean."
)

def build_prompt(original_lang: str, original_text: str, title: str | None = None, meta: dict | None = None) -> str:
    meta_line = f"메타데이터: {json.dumps(meta or {}, ensure_ascii=False)}"
    title_line = f"제목: {title or '(없음)'}"
    lang_note = "원문 언어: 영어" if original_lang == "en" else "원문 언어: 한국어"
    goals = (
        "- 원문이 한국어면 자연스러운 영어 번역 제공\n"
        "- 원문이 영어면 문법/어휘/자연스러움 교정 및 한국어 설명 제공\n"
        "- 기억해두면 좋은 어휘/표현 3~5개 추천\n"
    )
    return (
        f"{lang_note}\n{goals}\n{meta_line}\n{title_line}\n\n"
        f"---\n원문 시작\n{original_text}\n원문 끝\n"
        "JSON만 출력하세요."
    )

def _parse_json(text: str) -> Dict[str, Any]:
    try:
        data = json.loads(text)
    except Exception:
        data = {"raw": text}
    data.setdefault("translation", {})
    data.setdefault("corrections", {})
    data.setdefault("vocab_suggestions", [])
    return data

def analyze_with_openai(*, original_lang: str, original_text: str, title: str | None = None, meta: dict | None = None) -> Dict[str, Any]:
    prompt = build_prompt(original_lang, original_text, title=title, meta=meta)

    # 1) Responses API 우선 시도
    try:
        resp = client.responses.create(
            model=OPENAI_MODEL,
            instructions=SYSTEM_INSTRUCTION,
            input=prompt,
            timeout=OPENAI_TIMEOUT,
            response_format={"type": "json_object"},  # 일부 구버전 SDK에서 미지원
            max_output_tokens=800,
        )
        return _parse_json(resp.output_text)
    except TypeError:
        # 2) 구버전 SDK면 Chat Completions로 폴백
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
        return Response(
            {"detail": "OpenAI API 사용 한도를 초과했습니다. Billing 페이지를 확인해주세요."},
            status=status.HTTP_429_TOO_MANY_REQUESTS
        )
    except APIError as e:
        return Response(
            {"detail": f"OpenAI API 오류: {e.message}"},
            status=status.HTTP_502_BAD_GATEWAY
        )
