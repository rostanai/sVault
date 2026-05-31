"""Onboarding / first-run checklist schemas."""
from __future__ import annotations

from pydantic import BaseModel


class OnboardingStep(BaseModel):
    """A single first-run checklist step."""

    key: str
    label: str
    description: str
    done: bool
    href: str


class OnboardingStatus(BaseModel):
    """Full first-run checklist response."""

    steps: list[OnboardingStep]
    complete: bool
    completed_count: int
    total: int
