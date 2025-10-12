# entries/services.py
import os

def analyze_entry(entry) -> dict:
    """
    실제로는 OpenAI 등 LLM을 호출해 번역/교정/단어추천을 생성.
    지금은 더미 결과를 반환.
    """
    original_lang = entry.original_lang
    text = entry.original_text

    # 더미 로직
    translation = {
        "to": "en" if original_lang == "ko" else "ko",
        "text": "Dummy translation of the diary text."
    }
    corrections = {
        "corrected": "This is a corrected version of your text.",
        "explanations": [
            "Fixed verb tense for consistency.",
            "Replaced awkward phrasing with a more natural expression."
        ],
    }
    vocab = [
        {"word": "consistency", "meaning_ko": "일관성", "example_en": "Consistency beats perfection."},
        {"word": "resilience", "meaning_ko": "회복탄력성", "example_en": "Build resilience over time."},
    ]

    return {
        "translation": translation,
        "corrections": corrections,
        "vocab_suggestions": vocab,
        "model": "dummy-llm",
    }
