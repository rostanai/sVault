"""Calendar service — builds an RFC 5545 iCalendar (.ics) feed for policy renewals.

No third-party dependency: iCalendar is a simple line-based text format and we
hand-craft it to keep the dependency count low.

RFC 5545 rules applied:
- CRLF line endings throughout.
- All-day events use DTSTART;VALUE=DATE and DTEND;VALUE=DATE (exclusive end = next day).
- UID is globally unique: <policy_id>-expiry@svault or <policy_id>-renewal@svault.
- Text properties (SUMMARY, DESCRIPTION) have commas, semicolons, and embedded newlines
  escaped as \\, \\; and \\n respectively.
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

_CRLF = "\r\n"


def _escape(value: str) -> str:
    """Escape a text property value per RFC 5545 §3.3.11."""
    # Order matters: backslash first to avoid double-escaping.
    value = value.replace("\\", "\\\\")
    value = value.replace(";", "\\;")
    value = value.replace(",", "\\,")
    value = value.replace("\n", "\\n")
    value = value.replace("\r", "")
    return value


def _date_str(d: date) -> str:
    """Format a date as YYYYMMDD."""
    return d.strftime("%Y%m%d")


def _next_day(d: date) -> str:
    """Return the day after *d* formatted as YYYYMMDD (exclusive DTEND for all-day events)."""
    from datetime import timedelta
    return _date_str(d + timedelta(days=1))


def _dtstamp_now() -> str:
    """Return current UTC time in iCalendar DATE-TIME format (YYYYMMDDTHHMMSSZ)."""
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _vevent(
    uid: str,
    dtstart: date,
    summary: str,
    description: str,
    dtstamp: str,
) -> str:
    """Render a single VEVENT block (all-day) as a CRLF-terminated string."""
    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{dtstamp}",
        f"DTSTART;VALUE=DATE:{_date_str(dtstart)}",
        f"DTEND;VALUE=DATE:{_next_day(dtstart)}",
        f"SUMMARY:{_escape(summary)}",
        f"DESCRIPTION:{_escape(description)}",
        "END:VEVENT",
    ]
    return _CRLF.join(lines) + _CRLF


def _policy_description(policy: Any) -> str:
    """Build a human-readable DESCRIPTION from policy fields."""
    parts: list[str] = []
    if policy.category:
        parts.append(f"Category: {policy.category}")
    if policy.policy_number:
        parts.append(f"Policy No: {policy.policy_number}")
    if policy.sum_insured_inr is not None:
        parts.append(f"Sum Insured: INR {policy.sum_insured_inr:,.2f}")
    return "\n".join(parts)


def _policy_label(policy: Any) -> str:
    """Return policy_number if set, else category."""
    return policy.policy_number or policy.category or ""


def build_ics(policies: list[Any]) -> str:
    """Build a VCALENDAR string for the supplied policies.

    For each policy that has an expiry_date an all-day VEVENT is emitted.
    If the policy also has a renewal_date a second VEVENT is emitted for that date.
    Policies without an expiry_date are silently skipped.

    Returns a CRLF-delimited VCALENDAR string suitable for the text/calendar media type.
    """
    dtstamp = _dtstamp_now()

    header = (
        "BEGIN:VCALENDAR" + _CRLF
        + "VERSION:2.0" + _CRLF
        + "PRODID:-//sVault//Renewals//EN" + _CRLF
        + "CALSCALE:GREGORIAN" + _CRLF
        + "METHOD:PUBLISH" + _CRLF
    )
    footer = "END:VCALENDAR" + _CRLF

    event_blocks: list[str] = []

    for policy in policies:
        if not policy.expiry_date:
            continue

        label = _policy_label(policy)
        description = _policy_description(policy)

        # Primary event: expiry / renewal-due date.
        if label:
            expiry_summary = f"Renewal due: {policy.title} ({label})"
        else:
            expiry_summary = f"Renewal due: {policy.title}"
        event_blocks.append(
            _vevent(
                uid=f"{policy.id}-expiry@svault",
                dtstart=policy.expiry_date,
                summary=expiry_summary,
                description=description,
                dtstamp=dtstamp,
            )
        )

        # Optional second event: renewal_date (new policy start / payment date).
        if policy.renewal_date:
            if label:
                renewal_summary = f"Renewal date: {policy.title} ({label})"
            else:
                renewal_summary = f"Renewal date: {policy.title}"
            event_blocks.append(
                _vevent(
                    uid=f"{policy.id}-renewal@svault",
                    dtstart=policy.renewal_date,
                    summary=renewal_summary,
                    description=description,
                    dtstamp=dtstamp,
                )
            )

    return header + "".join(event_blocks) + footer
