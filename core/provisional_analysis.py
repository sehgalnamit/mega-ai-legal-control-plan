"""LLM-generated PROVISIONAL legal analysis for cases outside the
deterministic symbolic engine's rule coverage.

This is the one place in the architecture where the LLM is allowed to
produce prose *about* a legal outcome - but only as an explicitly
labeled, non-deterministic, lawyer-facing intake memo (never a final
verdict) that requires human sign-off before anyone relies on it. It
never substitutes for the symbolic engine when a domain IS covered by
`core.symbolic_engine` / `core.domain_router`.
"""
from __future__ import annotations

import os
from typing import Optional

PROVISIONAL_BANNER = "PROVISIONAL ANALYSIS - NOT A VERDICT - REQUIRES HUMAN LEGAL REVIEW"

SYSTEM_PROMPT = f"""You are an expert AI Legal Research and Intake Co-Pilot assisting a practicing
attorney during or immediately following a first client consultation. Your objective is NOT to
deliver a final court judgment or declare definitive legal outcomes. Your goal is to convert
messy, unstructured client facts into a structured, practitioner-ready Legal Intake & Tactical
Memorandum.

STRICT RULES:
1. Begin your response with the exact line:
   "{PROVISIONAL_BANNER}"
2. NO PREMATURE CONCLUSION: do NOT declare clauses "void", "illegal", or "enforceable" as
   absolute facts. Treat all client inputs as unverified claims. Use qualified terminology such
   as "prima facie unenforceable", "subject to fact-verification", "arguable defense", or
   "highly vulnerable to challenge". Never write "the court will rule...", "the clause is
   strictly void...", or "you will win/lose this case...".
3. Separate raw facts from missing evidence - if a key element required by governing case law is
   missing (e.g. trade secrets, geographical scope, consideration), flag it as a critical
   fact-gap.
4. Frame the analysis around what the LAWYER needs to do next: intake questions, documents to
   request, procedural deadlines to check, and tactical responses to draft.
5. Default jurisdiction is Singapore Common Law unless the facts state otherwise. Apply the
   relevant statutory frameworks (e.g. Limitation Act 1959, UCTA 1977) and leading case law
   objectively.
6. Structure the remainder of your response (after the banner line) into exactly these 4
   sections:
   ## 1. Case Overview & Key Facts
   - Parties, trigger event, and key chronology/monetary/contractual details stated by the client.
   ## 2. Preliminary Legal Assessment & Risk Mapping
   - Governing legal framework (statutes and landmark cases), strengths and red flags, and any
     procedural urgency (limitation periods, injunction risk, time-sensitive obligations).
   ## 3. Practitioner Intake & Document Checklist
   - A bulleted checklist of document requests and fact-gaps to probe during intake.
   ## 4. Immediate Tactical Next Steps
   - 2-4 actionable strategies: communication strategy, risk mitigation, procedural steps.
7. Keep the entire analysis concise (under 350 words total).
"""

_OFFLINE_FALLBACK = (
    f"{PROVISIONAL_BANNER}\n\n"
    "No deterministic rule module is loaded for this case's legal domain, and no "
    "live LLM endpoint is configured to draft a provisional analysis offline. "
    "Please escalate this case to a human reviewer, or configure GROQ_API_KEY / "
    "OPENAI_API_KEY / ANTHROPIC_API_KEY to enable a provisional draft."
)


def generate_provisional_analysis(
    case_text: str, usage_sink: Optional[dict] = None, domain_context: Optional[str] = None
) -> str:
    """Best-effort LLM draft analysis for a case with no deterministic rule
    coverage. Falls back to a safe static message when no LLM key is set.

    `domain_context` is an optional short string (matched Singapore legal
    domain(s), statutory codes, and precedents from `core.domain_taxonomy`)
    used to ground the draft rather than letting the model guess.
    """
    prompt = case_text if not domain_context else f"{case_text}\n\n[Reference context: {domain_context}]"

    for env_var, fn in (
        ("GROQ_API_KEY", _groq_analysis),
        ("OPENAI_API_KEY", _openai_analysis),
        ("ANTHROPIC_API_KEY", _anthropic_analysis),
    ):
        api_key = os.getenv(env_var)
        if api_key:
            try:
                return fn(prompt, api_key, usage_sink)
            except Exception:
                continue

    if usage_sink is not None:
        usage_sink.update(model="offline-no-provisional-analysis", input_tokens=0, output_tokens=0)
    return _OFFLINE_FALLBACK


def _chat_completion(
    case_text: str, api_key: str, base_url: Optional[str], model: str, usage_sink: Optional[dict]
) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        temperature=0.3,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": case_text},
        ],
    )
    if usage_sink is not None:
        usage = response.usage
        usage_sink.update(
            model=model,
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
        )
    return response.choices[0].message.content


def _groq_analysis(case_text: str, api_key: str, usage_sink: Optional[dict]) -> str:
    return _chat_completion(case_text, api_key, "https://api.groq.com/openai/v1", "llama-3.1-8b-instant", usage_sink)


def _openai_analysis(case_text: str, api_key: str, usage_sink: Optional[dict]) -> str:
    return _chat_completion(case_text, api_key, None, "gpt-4o-mini", usage_sink)


def _anthropic_analysis(case_text: str, api_key: str, usage_sink: Optional[dict]) -> str:
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=400,
        temperature=0.3,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": case_text}],
    )
    if usage_sink is not None:
        usage = response.usage
        usage_sink.update(
            model="claude-3-5-sonnet-20241022",
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
        )
    return response.content[0].text
