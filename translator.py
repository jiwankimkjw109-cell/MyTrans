import json
import os

import openai
from dotenv import load_dotenv
from openai import OpenAI

DEFAULT_MODEL = "gpt-6-astra"
MAX_CHARS = 5000
TEMPERATURE = 0.3

# temperature 지정을 거부한 모델 (프로세스 동안 기억)
_NO_TEMPERATURE_MODELS: set[str] = set()

# UI 표시 이름 -> JSON 키
LANGUAGES = {
    "영어": "english",
    "일본어": "japanese",
    "베트남어": "vietnamese",
}

# UI 표시 이름 -> 시스템 프롬프트에 추가할 지시
TONES = {
    "기본": "",
    "격식체": "- Use a formal, polite tone.\n",
    "친근체": "- Use a casual, friendly tone.\n",
}

SYSTEM_PROMPT = """You are a professional translator.
Detect the source language automatically and translate the user's text into the requested target languages.
- Preserve the original meaning, tone, line breaks, and formatting.
- Do not add explanations or notes.
{tone}- Return ONLY a JSON object with the keys: {target_keys}."""

# JSON 파싱 실패 시 언어별 개별 호출에 쓰는 프롬프트
SINGLE_PROMPT = """You are a professional translator.
Detect the source language automatically and translate the user's text into {language}.
- Preserve the original meaning, tone, line breaks, and formatting.
- Do not add explanations or notes.
{tone}- Return ONLY the translated text."""


class MissingAPIKeyError(Exception):
    pass


class ModelNotFoundError(Exception):
    def __init__(self, model: str):
        super().__init__(model)
        self.model = model


class TranslationError(Exception):
    pass


def get_config(name: str, default: str | None = None) -> str | None:
    """st.secrets(배포) -> .env(로컬) 순서로 설정값을 조회한다."""
    try:
        import streamlit as st

        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        # secrets.toml이 없으면 st.secrets 접근 시 예외가 발생한다
        pass

    load_dotenv()
    return os.getenv(name) or default


def _complete(client: OpenAI, model: str, system: str, text: str, json_mode: bool) -> str:
    def create():
        return client.chat.completions.create(
            model=model,
            temperature=openai.NOT_GIVEN if model in _NO_TEMPERATURE_MODELS else TEMPERATURE,
            response_format={"type": "json_object"} if json_mode else openai.NOT_GIVEN,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": text},
            ],
        )

    try:
        try:
            response = create()
        except openai.BadRequestError as e:
            # gpt-6-astra 등 기본값(1) 외 temperature를 거부하는 모델 -> 생략하고 재시도
            if getattr(e, "param", None) != "temperature" or model in _NO_TEMPERATURE_MODELS:
                raise
            _NO_TEMPERATURE_MODELS.add(model)
            response = create()
    except openai.NotFoundError as e:
        raise ModelNotFoundError(model) from e
    except openai.APIError as e:
        # 인증 실패, 타임아웃, 연결 오류, 요청 한도 초과 등
        raise TranslationError(str(e)) from e

    content = response.choices[0].message.content
    if not content:
        raise TranslationError("빈 응답")
    return content


def translate(text: str, languages: list[str], tone: str = "기본") -> dict[str, str]:
    """text를 languages(JSON 키 목록)로 번역해 {키: 번역문} 형태로 반환한다."""
    api_key = get_config("OPENAI_API_KEY")
    if not api_key:
        raise MissingAPIKeyError()

    client = OpenAI(api_key=api_key)
    model = get_config("OPENAI_MODEL", DEFAULT_MODEL)
    tone_rule = TONES.get(tone, "")

    system = SYSTEM_PROMPT.format(tone=tone_rule, target_keys=", ".join(languages))
    try:
        parsed = json.loads(_complete(client, model, system, text, json_mode=True))
        if not isinstance(parsed, dict):
            parsed = {}
    except json.JSONDecodeError:
        parsed = {}

    results = {}
    for key in languages:
        value = parsed.get(key)
        if isinstance(value, str) and value.strip():
            results[key] = value
        else:
            # JSON 파싱 실패 또는 해당 언어 누락 -> 개별 호출로 재시도
            system = SINGLE_PROMPT.format(language=key.capitalize(), tone=tone_rule)
            results[key] = _complete(client, model, system, text, json_mode=False).strip()
    return results
