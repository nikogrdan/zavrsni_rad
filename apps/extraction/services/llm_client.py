import logging
import time
from dataclasses import dataclass

from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    raw_text: str
    model_name: str
    latency_ms: int = None
    input_tokens: int = None
    output_tokens: int = None
    error: str = ""


class BaseLLMClient:
    def complete(self, system, user):
        raise NotImplementedError


class AnthropicClient(BaseLLMClient):
    def __init__(self, model=None):
        import anthropic

        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY nije postavljen u .env")
        self.model = model or settings.LLM_MODEL
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    def complete(self, system, user):
        started = time.monotonic()
        try:
            msg = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except Exception as exc:
            elapsed = int((time.monotonic() - started) * 1000)
            logger.error("Anthropic API error: %s", exc)
            return LLMResponse(
                raw_text="", model_name=self.model,
                latency_ms=elapsed, error=str(exc),
            )

        elapsed = int((time.monotonic() - started) * 1000)
        text = "".join(
            block.text for block in msg.content if block.type == "text"
        )
        return LLMResponse(
            raw_text=text,
            model_name=self.model,
            latency_ms=elapsed,
            input_tokens=msg.usage.input_tokens,
            output_tokens=msg.usage.output_tokens,
        )


class FakeLLMClient(BaseLLMClient):
    FIXTURES = {
        "zadaci za ovaj tjedan": """{"tasks": [
  {"title": "Poslati financijski izvještaj", "description": "",
   "due_at": "2026-08-22T14:00:00", "is_all_day": false,
   "assignee": "Niko", "confidence": 0.95},
  {"title": "Pripremiti prezentaciju za klijenta", "description": "",
   "due_at": "2026-08-24T09:00:00", "is_all_day": false,
   "assignee": "Ana", "confidence": 0.8},
  {"title": "Provjeriti ugovor s dobavljačem", "description": "",
   "due_at": "2026-08-19T00:00:00", "is_all_day": true,
   "assignee": "Marko", "confidence": 0.85}
]}""",

        "kava": '{"tasks": []}',

        "dokumentacija": """```json
{"tasks": [
  {"title": "Finalizirati dokumentaciju za projekt", "description": "",
   "due_at": "2026-08-24T00:00:00", "is_all_day": true,
   "assignee": "", "confidence": 0.45},
  {"title": "Nazvati Petru radi dogovora", "description": "",
   "due_at": "2026-09-02T00:00:00", "is_all_day": true,
   "assignee": "Niko", "confidence": 0.35}
]}
```""",

        "godišnji odmor": """{"tasks": [
  {"title": "Marko na godišnjem odmoru", "description": "",
   "due_at": "2026-08-25T00:00:00", "is_all_day": true,
   "assignee": "Marko", "confidence": 0.9}
]}""",

        "sastanak pomaknut": """{"tasks": [
  {"title": "Sastanak tima", "description": "Pomaknuto sa srijede",
   "due_at": "2026-08-20T10:00:00", "is_all_day": false,
   "assignee": "", "confidence": 0.7},
  {"title": "Potvrditi dolazak na sastanak", "description": "",
   "due_at": "2026-08-16T00:00:00", "is_all_day": true,
   "assignee": "Niko", "confidence": 0.6}
]}""",

        "ažuriranje projekta": """{"tasks": [
  {"title": "Predati tehničku specifikaciju", "description": "",
   "due_at": "2026-08-19T12:00:00", "is_all_day": false,
   "assignee": "Niko", "confidence": 0.92}
]}""",

        "sigurnosno upozorenje": '{"tasks": [{"title": "Provjeriti',
    }

    DEFAULT = '{"tasks": []}'

    def __init__(self, model=None):
        self.model = model or "fake-model"

    def complete(self, system, user):
        time.sleep(0.15)
        lowered = user.lower()
        raw = self.DEFAULT
        for key, fixture in self.FIXTURES.items():
            if key in lowered:
                raw = fixture
                break
        return LLMResponse(
            raw_text=raw,
            model_name=self.model,
            latency_ms=150,
            input_tokens=len(user) // 4,
            output_tokens=len(raw) // 4,
        )


def get_client(model=None):
    provider = settings.LLM_PROVIDER.lower()
    if provider == "fake":
        return FakeLLMClient(model=model)
    if provider == "anthropic":
        return AnthropicClient(model=model)
    raise ValueError(
        f"Nepoznat LLM_PROVIDER: '{provider}'. Koristi 'fake' ili 'anthropic'."
    )