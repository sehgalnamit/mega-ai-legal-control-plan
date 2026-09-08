"""Interactive procedural follow-up session helpers.

Defines the canonical "continue this session" prompt chips shown after a
legal memorandum, and assembles the case context passed to
`core.provisional_analysis.generate_procedural_followup` for whichever
chip the lawyer selects. Pure data/formatting helpers only - no LLM
calls and no legal judgment live here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.schemas import LegalCaseFactPayload


@dataclass(frozen=True)
class FollowupChip:
    key: str
    label: str


FOLLOWUP_CHIPS = (
    FollowupChip("draft_filing", "Draft the primary Court Application / Notice of Demand for this case."),
    FollowupChip("intake_checklist", "Generate the e-Litigation Document & Evidence Intake Checklist."),
    FollowupChip("procedural_timeline", "Detail the step-by-step court filing procedure and tactical timeline."),
)


def build_case_context(
    case_text: Optional[str],
    last_summary: Optional[str],
    payload: Optional[LegalCaseFactPayload] = None,
) -> str:
    """Assemble the context passed to a procedural follow-up drafting task
    from whatever the session has available: the original case narrative,
    the last rendered memo/summary, and any structured extracted facts.
    """
    parts = []
    if case_text:
        parts.append(f"Original case facts:\n{case_text}")
    if last_summary:
        parts.append(f"Prior analysis/summary already given to the lawyer:\n{last_summary}")
    if payload is not None:
        parts.append(f"Structured extracted facts:\n{payload.model_dump_json(indent=2)}")
    return "\n\n".join(parts) if parts else "No prior case context available."
