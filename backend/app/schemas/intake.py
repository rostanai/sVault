"""Policy auto-extraction schema — returned to the client for review before persisting."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.policy import PolicyCategory


class PolicyExtraction(BaseModel):
    """Structured fields extracted from an uploaded policy PDF by sVault AI.

    All domain fields are nullable — the client must review and fill in anything
    the AI could not reliably identify before calling POST /policies.
    `extracted_text_chars` and `notes` are always present.
    """

    category: PolicyCategory | None = Field(
        None,
        description="Detected policy category; one of the allowed enum values or null.",
    )
    title: str | None = Field(None, description="Policy name/title as stated in the document.")
    policy_number: str | None = Field(None, description="Unique policy number from the insurer.")
    insurer_name: str | None = Field(None, description="Name of the insurance company.")
    sum_insured_inr: str | None = Field(
        None,
        description="Sum insured in INR as a plain numeric string (no commas or currency symbol).",
    )
    premium_inr: str | None = Field(
        None,
        description="Annual premium in INR as a plain numeric string.",
    )
    gst_inr: str | None = Field(
        None,
        description="GST amount in INR as a plain numeric string.",
    )
    inception_date: str | None = Field(
        None,
        description="Policy start date in YYYY-MM-DD format, or null if not found.",
    )
    expiry_date: str | None = Field(
        None,
        description="Policy expiry date in YYYY-MM-DD format, or null if not found.",
    )
    extracted_text_chars: int = Field(
        ...,
        description="Number of characters of machine-readable text extracted from the PDF.",
    )
    notes: str | None = Field(
        None,
        description="Human-readable hint about extraction quality, e.g. scanned-document warning.",
    )
