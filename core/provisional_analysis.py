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
   sections - ALWAYS include all 4 section headers verbatim, even for a narrow follow-up
   question (e.g. a bare citation request) that is not a full case narrative; if a section has
   little to say for that kind of question, write one short line under it rather than omitting
   the header:
   ## 1. Case Overview & Key Facts
   - Parties, trigger event, and key chronology/monetary/contractual details stated by the client.
   ## 2. Preliminary Legal Assessment & Risk Mapping
   - Governing legal framework (statutes and landmark cases), strengths and red flags, and any
     procedural urgency (limitation periods, injunction risk, time-sensitive obligations).
   ## 3. Practitioner Intake & Document Checklist
   - A bulleted checklist of document requests and fact-gaps to probe during intake.
   ## 4. Immediate Tactical Next Steps
   - 2-4 actionable strategies: communication strategy, risk mitigation, procedural steps. Where
     relevant, name the likely Rules of Court 2021 filing track (e.g. Originating Claim for a
     disputed-facts action, Originating Application for a discrete/undisputed relief, or a
     Summons for an interlocutory application such as an injunction within an existing action),
     the supporting documents typically required (e.g. Statement of Claim, Supporting Affidavit,
     Certificate of Urgency for an expedited hearing), and any interim remedy that may be
     available (e.g. an ex parte Mareva injunction, an Expedited Protection Order). Always add
     that the exact filing track, forms, and deadlines must be confirmed against the current
     Rules of Court 2021, applicable Practice Directions, and the e-Litigation system before
     filing - never state a specific number of days for a procedural deadline unless it is a
     well-established statutory period (e.g. the Limitation Act 1959 limitation window).
7. Keep the entire analysis concise (under 400 words total).

SINGAPORE LEGAL LANDMARKS & GROUNDING TRUTHS
When a case touches one of these areas, ground your analysis in the actual holding below
(with accurate pinpoint paragraphs) rather than guessing or hedging that the law is unsettled:
- FINTECH / CRYPTO ASSETS: ByBit Fintech Ltd v Ho Kai Xin and others [2023] SGHC 199
  (Philip Jeyaretnam J) held, at [4] and [29]-[39] (conclusion at [36]), that USDT - and by
  extension crypto assets generally - are choses in action and therefore property capable of
  being held on trust; a constructive trust over the crypto asset was declared at [44]. Do not
  state that Singapore law leaves crypto/USDT property status undecided - cite this authority.
- RESTRAINT OF TRADE: Man Financial (S) Pte Ltd v Wong Bark Chuan David [2008] 1 SLR(R) 663
  applies a two-tier reasonableness test to restraint-of-trade clauses (reasonable as between
  the parties, and not contrary to the public interest).
- CONTRACT TERM CLASSIFICATION / TERMINATION: RDC Concrete Pte Ltd v Sato Kogyo (S) Pte Ltd
  [2007] 4 SLR(R) 413 governs whether a breached term is a condition (giving a right to
  terminate) or a warranty (damages only), including the "time is of the essence" analysis.
- INSOLVENCY CLAWBACK: Insolvency, Restructuring and Dissolution Act 2018 (IRDA) ss 224-226 -
  a transaction at an undervalue is voidable within the statutory look-back window, with
  insolvency statutorily presumed for connected-person transactions.
These are reference points to cite accurately when relevant - they do not override rule 2's
requirement to still qualify case-specific conclusions (e.g. limitation, standing, remedy
quantum) as provisional and subject to fact-verification. When citing a paragraph, paraphrase
its holding rather than presenting a verbatim quotation unless you are certain of the exact
wording.
"""

_OFFLINE_FALLBACK = (
    f"{PROVISIONAL_BANNER}\n\n"
    "No deterministic rule module is loaded for this case's legal domain, and no "
    "live LLM endpoint is configured to draft a provisional analysis offline. "
    "Please escalate this case to a human reviewer, or configure GROQ_API_KEY / "
    "OPENAI_API_KEY / ANTHROPIC_API_KEY to enable a provisional draft."
)

_REQUIRED_SECTION_HEADERS = (
    "## 1. Case Overview & Key Facts",
    "## 2. Preliminary Legal Assessment & Risk Mapping",
    "## 3. Practitioner Intake & Document Checklist",
    "## 4. Immediate Tactical Next Steps",
)


def _ensure_four_sections(text: str) -> str:
    """Deterministic safety net: narrow follow-up questions (e.g. a bare
    citation request) sometimes cause the LLM to skip the mandated 4-section
    structure even though the system prompt requires it. Rather than trust
    instruction-following alone, wrap any non-conforming response into the
    same 4 headers so every provisional analysis has an identical shape.
    """
    if all(header in text for header in _REQUIRED_SECTION_HEADERS):
        return text

    if text.startswith(PROVISIONAL_BANNER):
        body = text[len(PROVISIONAL_BANNER):].lstrip("\n").strip()
    else:
        body = text.strip()

    return (
        f"{PROVISIONAL_BANNER}\n\n"
        f"{_REQUIRED_SECTION_HEADERS[0]}\n"
        "- See the case facts referenced in the analysis below.\n\n"
        f"{_REQUIRED_SECTION_HEADERS[1]}\n"
        f"{body}\n\n"
        f"{_REQUIRED_SECTION_HEADERS[2]}\n"
        "- Verify the facts, citations, and authorities above against the client's instructions "
        "and the case file before relying on them.\n\n"
        f"{_REQUIRED_SECTION_HEADERS[3]}\n"
        "- Escalate to a human reviewer to confirm this analysis and determine next steps."
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
    result = _generate_with_fallback(SYSTEM_PROMPT, prompt, usage_sink, _OFFLINE_FALLBACK)
    return _ensure_four_sections(result)


def _generate_with_fallback(
    system_prompt: str, prompt: str, usage_sink: Optional[dict], offline_fallback: str
) -> str:
    """Shared Groq -> OpenAI -> Anthropic -> offline-fallback provider chain,
    parameterized by system prompt so the same fallback chain can drive both
    the case-assessment memo and the procedural follow-up drafting tasks.
    """
    for env_var, fn in (
        ("GROQ_API_KEY", _groq_chat),
        ("OPENAI_API_KEY", _openai_chat),
        ("ANTHROPIC_API_KEY", _anthropic_chat),
    ):
        api_key = os.getenv(env_var)
        if api_key:
            try:
                return fn(system_prompt, prompt, api_key, usage_sink)
            except Exception:
                continue

    if usage_sink is not None:
        usage_sink.update(model="offline-no-provisional-analysis", input_tokens=0, output_tokens=0)
    return offline_fallback


def _chat_completion(
    system_prompt: str, case_text: str, api_key: str, base_url: Optional[str], model: str, usage_sink: Optional[dict]
) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
    # gpt-oss on Groq is a reasoning model that shares its completion budget between hidden
    # reasoning and visible content - cap reasoning effort so content isn't left empty.
    extra_body = {"reasoning_effort": "low"} if base_url else {}
    response = client.chat.completions.create(
        model=model,
        temperature=0.3,
        max_tokens=1200,
        extra_body=extra_body,
        messages=[
            {"role": "system", "content": system_prompt},
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


def _groq_chat(system_prompt: str, case_text: str, api_key: str, usage_sink: Optional[dict]) -> str:
    return _chat_completion(
        system_prompt, case_text, api_key, "https://api.groq.com/openai/v1", "openai/gpt-oss-20b", usage_sink
    )


def _openai_chat(system_prompt: str, case_text: str, api_key: str, usage_sink: Optional[dict]) -> str:
    return _chat_completion(system_prompt, case_text, api_key, None, "gpt-4o-mini", usage_sink)


def _anthropic_chat(system_prompt: str, case_text: str, api_key: str, usage_sink: Optional[dict]) -> str:
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=900,
        temperature=0.3,
        system=system_prompt,
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


PROCEDURAL_FOLLOWUP_BANNER = "DRAFT WORK PRODUCT - NOT FILED - REQUIRES ATTORNEY REVIEW BEFORE USE"

_PROCEDURAL_CAVEAT = (
    "Use bracketed [PLACEHOLDER] text for any name, date, amount, or fact not explicitly given. "
    "Never invent a specific number of days for a court deadline unless it is a well-established "
    "statutory period (e.g. the Limitation Act 1959 window); otherwise describe the step "
    "qualitatively and instruct the lawyer to confirm the exact timeframe against the current "
    "Rules of Court 2021, applicable Practice Directions, and the e-Litigation system before "
    "relying on it. POHA refers to the Protection from Harassment Act 2014 - never expand it as "
    "any other statute name. This is a drafting aid, not a filed or verified document."
)

_FOLLOWUP_SYSTEM_PROMPTS: dict = {
    "draft_filing": f"""You are a litigation drafting assistant helping a Singapore-qualified
attorney prepare a first-draft skeleton of the primary court application or pre-action letter for
a case, under the Rules of Court 2021 / e-Litigation system.

STRICT RULES:
1. Begin your response with the exact line: "{PROCEDURAL_FOLLOWUP_BANNER}"
2. First draft a short Notice of Demand / pre-action letter of demand skeleton, then a skeleton
   of the primary originating process: state whether an Originating Claim (facts in dispute,
   adversarial) or an Originating Application (undisputed facts / a discrete relief) is the
   likelier fit given the pleaded facts, and outline the key paragraphs it would need (parties,
   relief sought, brief facts). If urgent interim relief is indicated by the facts (e.g. an
   injunction), add a skeleton Supporting Affidavit outline (deponent, exhibits, urgency grounds).
3. {_PROCEDURAL_CAVEAT}
4. Keep the entire draft under 450 words.
""",
    "intake_checklist": f"""You are a litigation support assistant helping a Singapore-qualified
attorney prepare an e-Litigation document and evidence intake checklist for a case.

STRICT RULES:
1. Begin your response with the exact line: "{PROCEDURAL_FOLLOWUP_BANNER}"
2. Produce a bulleted checklist grouped under: (a) Documents to obtain from the client, (b)
   Documents/evidence to obtain from third parties or via discovery, (c) Affidavit exhibits and
   how they should be marked/numbered, (d) Any missing facts that must be verified before filing.
   Tailor the checklist to the specific case facts and statutory framework given.
3. {_PROCEDURAL_CAVEAT}
4. Keep the entire checklist under 400 words.
""",
    "procedural_timeline": f"""You are a litigation support assistant helping a Singapore-qualified
attorney understand the likely court filing procedure and tactical timeline for a case, under the
Rules of Court 2021 / e-Litigation system.

STRICT RULES:
1. Begin your response with the exact line: "{PROCEDURAL_FOLLOWUP_BANNER}"
2. Set out the sequence of procedural steps qualitatively (e.g. pre-action letter of demand ->
   filing the originating process via e-Litigation -> service -> the other side's response ->
   any interlocutory applications (e.g. injunction, striking out) -> case conference -> hearing/
   trial), noting which State Courts / General Division of the High Court forum is likely given
   the claim value or relief sought, and flagging any genuinely time-critical step (e.g. urgent
   interim relief given an ongoing safety risk).
3. {_PROCEDURAL_CAVEAT}
4. Keep the entire timeline under 400 words.
""",
}

_FOLLOWUP_OFFLINE_FALLBACK = (
    f"{PROCEDURAL_FOLLOWUP_BANNER}\n\n"
    "No live LLM endpoint is configured to draft this follow-up offline. Please configure "
    "GROQ_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY, or ask a human reviewer to prepare this "
    "document."
)


def generate_procedural_followup(task_key: str, case_context: str, usage_sink: Optional[dict] = None) -> str:
    """Draft one of the interactive procedural follow-ups (draft filing skeleton,
    intake checklist, or filing timeline) for a case already analyzed by
    `generate_provisional_analysis` or the deterministic symbolic engine.

    This is drafting assistance, not legal advice or a filed document - every
    task system prompt carries its own `PROCEDURAL_FOLLOWUP_BANNER` and
    verification caveat.
    """
    system_prompt = _FOLLOWUP_SYSTEM_PROMPTS.get(task_key)
    if system_prompt is None:
        raise ValueError(f"Unknown procedural follow-up task: {task_key!r}")
    return _generate_with_fallback(system_prompt, case_context, usage_sink, _FOLLOWUP_OFFLINE_FALLBACK)
