"""Policy PDF auto-extraction service — stateless, no DB writes.

Extracts machine-readable text from a PDF upload, then asks sVault AI to
return a structured JSON of policy fields for the user to review.

The underlying LLM provider is never surfaced to the caller; all user-facing
text uses the brand name "sVault AI".
"""
from __future__ import annotations

import io
import json
import logging
from typing import get_args

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.schemas.policy import PolicyCategory

log = logging.getLogger("svault.extraction")

# The full set of allowed category values, sent verbatim to the AI so it can
# pick exactly one (or null).
_CATEGORIES: tuple[str, ...] = get_args(PolicyCategory)

# Maximum characters of PDF text forwarded to the AI (controls token spend).
_MAX_TEXT_CHARS = 12_000

_SYSTEM_PROMPT = (
    "You are sVault AI, an expert at reading Indian corporate insurance policy documents. "
    "The user will provide extracted text from a PDF. "
    "Return ONLY a valid JSON object (no markdown, no prose) with exactly these keys:\n"
    "  category, title, policy_number, insurer_name, sum_insured_inr, premium_inr, "
    "gst_inr, inception_date, expiry_date\n\n"
    "Rules:\n"
    "- Use null for any field you cannot find with confidence.\n"
    f"- category MUST be one of {list(_CATEGORIES)} (inferred from content) or null.\n"
    "- Amounts (sum_insured_inr, premium_inr, gst_inr): plain numeric string, "
    "no commas, no currency symbols (e.g. \"5000000\").\n"
    "- Dates (inception_date, expiry_date): YYYY-MM-DD format or null.\n"
    "- Do NOT invent values. Extract only what is explicitly stated in the text.\n"
    "- Never include extra keys."
)

_SCANNED_NOTES = (
    "No machine-readable text found — this looks like a scanned document. "
    "OCR isn't supported yet; please enter the details manually."
)

_PARSE_FAILURE_NOTES = (
    "sVault AI returned a response that could not be parsed as JSON. "
    "Please enter the policy details manually."
)


def _extract_text(raw: bytes, mime: str | None) -> str:
    """Extract plain text from PDF bytes using pypdf.

    Returns an empty string for non-PDF MIME types or when extraction fails.
    Mirrors the same helper in rag_service.py.
    """
    if mime and "pdf" not in mime:
        return ""
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(raw))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as exc:  # pragma: no cover
        log.warning("pdf_extract_failed: %s", exc)
        return ""


def _null_result(char_count: int = 0, notes: str | None = None) -> dict:
    """Return a fully-null extraction result (scanned doc or parse failure)."""
    return {
        "category": None,
        "title": None,
        "policy_number": None,
        "insurer_name": None,
        "sum_insured_inr": None,
        "premium_inr": None,
        "gst_inr": None,
        "inception_date": None,
        "expiry_date": None,
        "extracted_text_chars": char_count,
        "notes": notes,
    }


def _sanitise_ai_output(raw_json: dict, char_count: int) -> dict:
    """Validate and sanitise the AI's JSON payload into the extraction schema shape.

    - Validates that `category` is one of the allowed enum values; sets null otherwise.
    - Strips unexpected keys.
    - Sets `extracted_text_chars` to the real value.
    """
    allowed_fields = {
        "category", "title", "policy_number", "insurer_name",
        "sum_insured_inr", "premium_inr", "gst_inr",
        "inception_date", "expiry_date",
    }
    result: dict = {k: raw_json.get(k) for k in allowed_fields}

    # Validate category against the allowed Literal set.
    if result.get("category") not in _CATEGORIES:
        result["category"] = None

    result["extracted_text_chars"] = char_count
    result["notes"] = None
    return result


async def extract_policy_fields(
    raw: bytes, mime: str | None, api_key: str | None = None
) -> dict:
    """Extract structured policy fields from raw PDF bytes.

    Steps:
    1. Extract text with pypdf.
    2. If no text found, return a null result with a scanned-doc note.
    3. If sVault AI is unconfigured, raise AppError(internal_error).
    4. Otherwise call sVault AI in JSON mode, parse the response, sanitise it.

    ``api_key`` lets the caller pass a key resolved from platform_settings; falls
    back to the env-configured key. Returns a dict matching ``PolicyExtraction``.
    Raises ``AppError`` on configuration or upstream failures.
    """
    text_content = _extract_text(raw, mime)
    char_count = len(text_content)

    if not text_content.strip():
        return _null_result(char_count=0, notes=_SCANNED_NOTES)

    resolved_key = api_key or settings.svault_ai_api_key
    if not resolved_key:
        raise AppError(ErrorCode.internal_error, "sVault AI is not configured")

    # Cap text forwarded to the AI to control token spend.
    capped_text = text_content[:_MAX_TEXT_CHARS]
    user_message = (
        f"Extract the insurance policy details from the following document text:\n\n{capped_text}"
    )

    try:
        # Lazy import — keeps `openai` (and its httpx/anyio deps) off the cold-start path
        # for requests that never extract. Mirrors rag_service.ask().
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=resolved_key,
            base_url=settings.svault_ai_base_url,
        )
        resp = await client.chat.completions.create(
            model=settings.svault_ai_model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
        )
        ai_text = resp.choices[0].message.content or ""
    except Exception as exc:
        log.warning("svault_ai_extraction_failed: %s", exc)
        raise AppError(ErrorCode.upstream_error, "sVault AI is unavailable") from exc

    # Robustly parse the JSON response.
    try:
        raw_json = json.loads(ai_text)
        if not isinstance(raw_json, dict):
            raise ValueError("Expected a JSON object")
    except (json.JSONDecodeError, ValueError) as exc:
        log.warning("svault_ai_parse_failed (got: %.200s): %s", ai_text, exc)
        return _null_result(char_count=char_count, notes=_PARSE_FAILURE_NOTES)

    return _sanitise_ai_output(raw_json, char_count)
