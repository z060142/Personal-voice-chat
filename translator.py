import os

from openai import OpenAI

LANG_NAMES = {
    "zh": "Chinese",
    "en": "English",
    "ja": "Japanese",
    "ko": "Korean",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "it": "Italian",
    "ru": "Russian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "ar": "Arabic",
    "th": "Thai",
    "vi": "Vietnamese",
    "id": "Indonesian",
}

_BASE_SYSTEM = (
    "You are a real-time voice translator for online gaming sessions. "
    "Translate naturally and concisely, preserving gaming slang, callouts, and emotional tone. "
    "{context}"
    "Rules: (1) Output ONLY the translated text, nothing else. "
    "(2) Keep proper nouns, map names, and unit names untranslated when ambiguous. "
    "(3) Match the urgency and brevity of the original."
)


class Translator:
    def __init__(self, api_key: str = None, model: str = "openai/gpt-4o", game_context: str = ""):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key or os.environ["OPENROUTER_API_KEY"],
        )
        self.model = model
        ctx = f"Game: {game_context}. " if game_context.strip() else ""
        self._system = _BASE_SYSTEM.format(context=ctx)

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        if not text.strip():
            return ""
        src = LANG_NAMES.get(source_lang, source_lang)
        tgt = LANG_NAMES.get(target_lang, target_lang)
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self._system},
                {"role": "user", "content": f"Translate from {src} to {tgt}:\n{text}"},
            ],
            temperature=0.3,
            max_tokens=512,
        )
        return resp.choices[0].message.content.strip()
