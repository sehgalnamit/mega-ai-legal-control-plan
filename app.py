"""Mega AI (Singapore Legal Control Plane) - Real-Time Legal Chatbot.

Enforces the neuro-symbolic + GovOps architecture on every chat turn:
Neural Parsing -> Graph Gate -> MAS SAFR Envelope -> Symbolic Deduction
-> Procedural Calculator -> GovOps Telemetry (traces, FinOps, audit log).
"""
from __future__ import annotations

import json
import uuid

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from core.chat_router import generate_generic_reply, is_legal_case_message
from core.domain_router import build_skipped_deduction_notice, classify_domains, is_unmapped_domain
from core.domain_taxonomy import build_unmapped_domain_response, classify_singapore_legal_domains
from core.followup_intent import detect_fact_patch
from core.govops.finops import (
    MAX_ITERATIONS_PER_CONVERSATION,
    FinOpsLedger,
    IterationCapExceededError,
    TokenBudgetExceededError,
    check_iteration_cap,
)
from core.govops.safr_envelope import SafrDisposition, evaluate_safr_envelope
from core.govops.extraction_validator import ConsistencyCheckResult, validate_extraction_consistency
from core.govops.tracer import (
    build_span_tree,
    get_captured_spans,
    inject_traceparent,
    reset_trace_buffer,
    set_disposition,
    start_root_span,
    start_worker_span,
)
from core.graph_gate import check_precedent_status
from core.neural_parser import parse_legal_case_text
from core.procedural_calculators import (
    check_limitation_period,
    check_liquidated_damages_penalty,
    check_undervalue_transaction,
    evaluate_poha_harassment_claim,
)
from core.provisional_analysis import generate_provisional_analysis
from core.response_renderer import render_legal_advice_summary
from core.safety.content_moderation import check_content_safety
from core.symbolic_engine import run_symbolic_deduction

st.set_page_config(page_title="Mega AI - Singapore Legal Chatbot", layout="wide")

AIRCON_DISPUTE_SAMPLE = (
    "Client A leased a commercial property to Client B under a standard form lease "
    "with unequal bargaining power. Client B stopped paying rent because the main "
    "VRV central aircon system broke down in June 2024, causing S$45,000 in spoiled "
    "perishable inventory and severe heat discomfort. The lease contains Clause 14, "
    "a standard form exemption clause, excluding all landlord liability for property "
    "damage caused by equipment breakdown, and Clause 18 stating aircon maintenance "
    "is a warranty. No inducement was offered for these terms. Client B wants to "
    "terminate the lease immediately and claim damages. The contract was breached on "
    "2024-06-15. Cited precedent: RDC Concrete Pte Ltd v Sato Kogyo (S) Pte Ltd "
    "[2007] 4 SLR(R) 413."
)

RESTRAINT_OF_TRADE_SAMPLE = (
    "Client C was employed as a Junior Software Developer by TechCorp SG (a "
    "Singapore-based software company) under a standard employment contract signed "
    "in 2024. Client C's monthly salary was S$4,500. Clause 22 (Restraint of Trade) "
    "stipulates: 'Upon termination of employment for any reason, the Employee shall "
    "not work for, consult with, or establish any business competing with TechCorp "
    "SG anywhere in the Asia-Pacific region for a period of 24 months.' No specialized "
    "trade secrets or confidential client lists were accessible to Client C in their "
    "junior role.\n\nOn 2026-03-01, Client C resigned and accepted a job offer as a "
    "Web Developer at a rival Singapore fintech startup. TechCorp SG has issued a "
    "Letter of Demand threatening an interim injunction to enforce Clause 22 and "
    "claim liquidated damages under Clause 23 (S$100,000 fixed penalty).\n\n"
    "Governing Frameworks & Precedents:\n\n"
    "Man Financial (S) Pte Ltd v Wong Bark Chuan David [2008] 1 SLR(R) 663 (Singapore "
    "Court of Appeal test for Restraint of Trade).\n\n"
    "Denka Advantech Pte Ltd v Tan Yuanyuan [2020] 2 SLR 1155 (Penalty rule in "
    "Singapore)."
)

if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "iteration_count" not in st.session_state:
    st.session_state.iteration_count = 0
if "audit_log" not in st.session_state:
    st.session_state.audit_log = []
if "last_case_payload" not in st.session_state:
    st.session_state.last_case_payload = None


def _evaluate_case_payload(payload, provisional_source_text, ledger, root_span, run_validator=True):
    """Run graph gate, domain classification, SAFR envelope, symbolic
    deduction, procedural calculators, and (if the domain is unmapped) a
    provisional LLM analysis for one legal-case payload.

    Returns (summary, verdict_card, safr_panel_fields).
    """
    with start_worker_span("graph_gate", "execute_tool", "graph_gate"):
        graph_result = check_precedent_status(payload.cited_precedent)
        additional_graph_results = [check_precedent_status(c) for c in payload.additional_precedents]

    if run_validator:
        with start_worker_span("extraction_validator", "execute_tool", "extraction_validator"):
            consistency_result = validate_extraction_consistency(payload, provisional_source_text)
    else:
        consistency_result = ConsistencyCheckResult(is_consistent=True, contradictions=[])

    with start_worker_span("domain_router", "execute_tool", "domain_router"):
        domains_evaluated = classify_domains(payload)
        unmapped = is_unmapped_domain(payload)

    safr_result = evaluate_safr_envelope(
        payload,
        extraction_confidence=payload.extraction_confidence,
        claim_value_usd=payload.claim_value_sgd,
        extraction_contradictions=consistency_result.contradictions,
        is_unmapped_domain=unmapped,
    )
    set_disposition(root_span, safr_result.verdict)

    deduction = None
    limitation = None
    penalty_check = None
    undervalue_check = None
    poha_check = None
    provisional_text = None
    unmapped_domain_analysis = None
    matched_domains = []
    if safr_result.disposition != SafrDisposition.DENY:
        if unmapped:
            # No deterministic rule module covers this domain - skip Spandeck/
            # UCTA/RDC Concrete/restraint-of-trade deduction entirely rather
            # than emitting a misleading proof trace for an irrelevant test.
            with start_worker_span("domain_taxonomy", "execute_tool", "domain_taxonomy"):
                matched_domains = classify_singapore_legal_domains(provisional_source_text)
                unmapped_domain_analysis = build_unmapped_domain_response(matched_domains, payload.case_id)

            deduction = build_skipped_deduction_notice([d.label for d in matched_domains])
            deduction["case_id"] = payload.case_id
        else:
            with start_worker_span("symbolic_deduction", "execute_tool", "symbolic_engine"):
                deduction = run_symbolic_deduction(payload)

        if payload.contract_breach_date:
            with start_worker_span("limitation_calculator", "execute_tool", "procedural_calculator"):
                limitation = check_limitation_period(payload.contract_breach_date)

        if payload.monthly_salary_sgd and payload.liquidated_damages_sgd:
            with start_worker_span("penalty_clause_calculator", "execute_tool", "procedural_calculator"):
                penalty_check = check_liquidated_damages_penalty(
                    payload.monthly_salary_sgd, payload.liquidated_damages_sgd
                )

        if (
            payload.has_insolvency_clawback_claim
            and payload.asset_market_value_sgd is not None
            and payload.consideration_paid_sgd is not None
            and payload.transaction_date is not None
            and payload.winding_up_date is not None
        ):
            with start_worker_span("undervalue_transaction_calculator", "execute_tool", "procedural_calculator"):
                undervalue_check = check_undervalue_transaction(
                    payload.asset_market_value_sgd,
                    payload.consideration_paid_sgd,
                    payload.is_connected_person,
                    payload.transaction_date,
                    payload.winding_up_date,
                )

        if payload.has_harassment_claim:
            with start_worker_span("poha_harassment_calculator", "execute_tool", "procedural_calculator"):
                poha_check = evaluate_poha_harassment_claim(
                    payload.publishes_identifying_information,
                    payload.urges_third_party_harassment,
                    payload.causes_alarm_distress_or_fear,
                )
        else:
            poha_check = None

        if unmapped:
            domain_context = None
            if matched_domains:
                statutes = ", ".join(unmapped_domain_analysis["matched_statutory_codes"]) or "none identified"
                precedents = ", ".join(unmapped_domain_analysis["matched_precedents"]) or "none identified"
                domain_context = (
                    f"Matched Singapore legal domain(s): {', '.join(d.label for d in matched_domains)}. "
                    f"Statutory codes: {statutes}. Precedents: {precedents}."
                )

            provisional_usage: dict = {}
            with start_worker_span("provisional_analysis", "chat", "dynamic_synthesizer"):
                provisional_text = generate_provisional_analysis(
                    provisional_source_text, usage_sink=provisional_usage, domain_context=domain_context
                )
            ledger.record(
                "provisional_analysis",
                provisional_usage.get("model", "offline-no-provisional-analysis"),
                provisional_usage.get("input_tokens", 0),
                provisional_usage.get("output_tokens", 0),
            )

    if safr_result.disposition == SafrDisposition.DENY:
        summary = "🚫 This request was **denied** by the MAS SAFR governance envelope: " + "; ".join(
            safr_result.reasons
        )
    elif unmapped:
        matched_labels = (
            ", ".join(d.label for d in matched_domains) if matched_domains else "unclassified"
        )
        summary = (
            f"🧭 **No deterministic rule module is loaded for this case's legal domain(s) ({matched_labels}).** "
            "Escalating to human review with a provisional analysis below.\n\n"
            f"{provisional_text}"
        )
    else:
        summary = render_legal_advice_summary(
            payload,
            deduction,
            limitation,
            graph_result,
            penalty_check=penalty_check,
            undervalue_check=undervalue_check,
            poha_check=poha_check,
            additional_graph_results=additional_graph_results,
        )
        if safr_result.disposition == SafrDisposition.ESCALATE:
            summary = "🧑‍⚖️ **Escalated for human-in-the-loop review.** " + summary

    verdict_card = {
        "case_id": payload.case_id,
        "extracted_facts": payload.model_dump(),
        "domains_evaluated": domains_evaluated,
        "is_unmapped_domain": unmapped,
        "unmapped_domain_analysis": unmapped_domain_analysis,
        "graph_gate": graph_result,
        "additional_precedent_checks": additional_graph_results,
        "extraction_consistency": vars(consistency_result),
        "symbolic_deduction": deduction,
        "limitation_check": limitation,
        "penalty_check": penalty_check,
        "undervalue_transaction_check": undervalue_check,
        "poha_harassment_check": poha_check,
        "provisional_analysis": provisional_text,
    }
    safr_panel_fields = {
        "safr_disposition": safr_result.disposition.value,
        "safr_verdict": safr_result.verdict,
        "safr_reasons": safr_result.reasons,
    }
    return summary, verdict_card, safr_panel_fields

with st.sidebar:
    st.header("Session / GovOps Controls")
    enduser_id = st.text_input("enduser.id", value="lawyer_session_1")
    token_budget = st.number_input("FinOps token budget cap", min_value=1000, value=20_000, step=1000)
    practitioner_view = st.checkbox(
        "\U0001f469\u200d\u2696\ufe0f Practitioner View (hide diagnostic/GovOps panels)", value=False
    )
    st.caption(f"gen_ai.conversation.id: `{st.session_state.conversation_id}`")
    st.caption(f"Iterations: {st.session_state.iteration_count} / {MAX_ITERATIONS_PER_CONVERSATION}")
    if st.button("Reset conversation"):
        st.session_state.conversation_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.session_state.iteration_count = 0
        st.session_state.audit_log = []
        st.session_state.last_case_payload = None
        st.rerun()

st.title("⚖️ Mega AI — Singapore Legal Control Plane Chatbot")
st.caption(
    "Neuro-Symbolic pipeline with MAS SAFR governance, W3C trace propagation, and "
    "real-time FinOps cost tracking on every turn."
)

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if not practitioner_view:
            if message.get("verdict_card"):
                with st.expander("Deterministic Verdict Card"):
                    st.json(message["verdict_card"])
            if message.get("govops_panel"):
                with st.expander("GovOps & Telemetry Panel"):
                    st.json(message["govops_panel"])

prompt = st.chat_input("Describe the dispute (e.g. the aircon maintenance scenario)...")

if not st.session_state.messages and not prompt:
    st.info("💡 Try a sample dispute, or type your own scenario in the chat box below.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Use sample aircon dispute"):
            prompt = AIRCON_DISPUTE_SAMPLE
    with col2:
        if st.button("Use sample restraint-of-trade dispute"):
            prompt = RESTRAINT_OF_TRADE_SAMPLE

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    try:
        check_iteration_cap(st.session_state.iteration_count, MAX_ITERATIONS_PER_CONVERSATION)
    except IterationCapExceededError as exc:
        with st.chat_message("assistant"):
            st.error(str(exc))
        st.stop()

    st.session_state.iteration_count += 1
    moderation = check_content_safety(prompt)
    last_payload = st.session_state.last_case_payload
    fact_patch = detect_fact_patch(prompt) if last_payload is not None and len(prompt.split()) < 40 else None

    if not moderation.is_safe:
        refusal = (
            "🚫 I can't help with that request — it was flagged by the content-safety "
            f"guardrail (categories: {', '.join(moderation.categories) or 'unspecified'}). "
            "Please rephrase your message."
        )
        with st.chat_message("assistant"):
            st.error(refusal)
        st.session_state.messages.append({"role": "assistant", "content": refusal})
        st.session_state.audit_log.append(
            {
                "case_id": None,
                "prompt": prompt,
                "verdict_card": None,
                "govops_panel": {"moderation": moderation.__dict__, "safr_disposition": "DENY"},
            }
        )

    elif fact_patch is not None:
        # Stateful multi-turn HITL follow-up: re-evaluate the previous
        # case with a small set of facts patched, instead of re-parsing
        # a brand new case from a short follow-up message.
        reset_trace_buffer()
        ledger = FinOpsLedger(max_token_budget=int(token_budget))
        case_id = f"{last_payload.case_id}-rev{st.session_state.iteration_count}"
        patched_payload = last_payload.model_copy(update={**fact_patch.field_updates, "case_id": case_id})

        with st.chat_message("assistant"):
            try:
                with start_root_span(st.session_state.conversation_id, enduser_id, prompt) as root_span:
                    traceparent = inject_traceparent().get("traceparent", "")
                    summary, verdict_card, safr_panel_fields = _evaluate_case_payload(
                        patched_payload, prompt, ledger, root_span, run_validator=False
                    )

                spans = get_captured_spans()
                span_tree = build_span_tree(spans)
                trace_id = span_tree[0]["trace_id"] if span_tree else None

                summary = f"🔁 **Re-evaluating with updated facts** ({fact_patch.description}).\n\n" + summary
                govops_panel = {
                    "trace_id": trace_id,
                    "traceparent": traceparent,
                    "finops": ledger.to_dict(),
                    "span_tree": span_tree,
                    **safr_panel_fields,
                }

                st.session_state.audit_log.append(
                    {
                        "case_id": patched_payload.case_id,
                        "prompt": prompt,
                        "verdict_card": verdict_card,
                        "govops_panel": govops_panel,
                    }
                )
                st.session_state.last_case_payload = patched_payload

                st.markdown(summary)
                if not practitioner_view:
                    with st.expander("Deterministic Verdict Card"):
                        st.json(verdict_card)
                    with st.expander("GovOps & Telemetry Panel"):
                        st.json(govops_panel)

                st.session_state.messages.append(
                    {"role": "assistant", "content": summary, "verdict_card": verdict_card, "govops_panel": govops_panel}
                )

            except TokenBudgetExceededError as exc:
                error_message = f"🔴 FinOps circuit breaker tripped: {exc}"
                st.error(error_message)
                st.session_state.messages.append({"role": "assistant", "content": error_message})

    elif not is_legal_case_message(prompt):
        reset_trace_buffer()
        ledger = FinOpsLedger(max_token_budget=int(token_budget))
        with st.chat_message("assistant"):
            with start_root_span(st.session_state.conversation_id, enduser_id, prompt) as root_span:
                set_disposition(root_span, "ALLOW")
                usage_sink: dict = {}
                with start_worker_span("generic_chat_reply", "chat", "chat_router") as reply_span:
                    reply = generate_generic_reply(prompt, usage_sink=usage_sink)
                    ledger.record(
                        "generic_chat_reply",
                        usage_sink.get("model", "offline-canned-reply"),
                        usage_sink.get("input_tokens", 0),
                        usage_sink.get("output_tokens", 0),
                    )
                    reply_span.set_attribute("gen_ai.usage.input_tokens", usage_sink.get("input_tokens", 0))
                    reply_span.set_attribute("gen_ai.usage.output_tokens", usage_sink.get("output_tokens", 0))

            govops_panel = {
                "safr_disposition": "AUTO_EXECUTE",
                "finops": ledger.to_dict(),
                "span_tree": build_span_tree(get_captured_spans()),
            }
            st.markdown(reply)
            if not practitioner_view:
                with st.expander("GovOps & Telemetry Panel"):
                    st.json(govops_panel)

        st.session_state.messages.append({"role": "assistant", "content": reply, "govops_panel": govops_panel})
        st.session_state.audit_log.append(
            {"case_id": None, "prompt": prompt, "verdict_card": None, "govops_panel": govops_panel}
        )

    else:
        reset_trace_buffer()
        ledger = FinOpsLedger(max_token_budget=int(token_budget))
        case_id = f"CASE_{st.session_state.iteration_count}_{st.session_state.conversation_id[:8]}"

        with st.chat_message("assistant"):
            try:
                with start_root_span(st.session_state.conversation_id, enduser_id, prompt) as root_span:
                    traceparent = inject_traceparent().get("traceparent", "")

                    usage_sink: dict = {}
                    with start_worker_span(
                        "neural_parsing", "chat", "neural_parser", **{"gen_ai.request.model": "auto"}
                    ) as parser_span:
                        payload = parse_legal_case_text(prompt, case_id=case_id, usage_sink=usage_sink)
                        ledger.record(
                            "neural_parsing",
                            usage_sink.get("model", "mock-offline-parser"),
                            usage_sink.get("input_tokens", 0),
                            usage_sink.get("output_tokens", 0),
                        )
                        parser_span.set_attribute("gen_ai.usage.input_tokens", usage_sink.get("input_tokens", 0))
                        parser_span.set_attribute("gen_ai.usage.output_tokens", usage_sink.get("output_tokens", 0))

                    st.session_state.last_case_payload = payload

                    summary, verdict_card, safr_panel_fields = _evaluate_case_payload(
                        payload, prompt, ledger, root_span, run_validator=True
                    )

                spans = get_captured_spans()
                span_tree = build_span_tree(spans)
                trace_id = span_tree[0]["trace_id"] if span_tree else None

                govops_panel = {
                    "trace_id": trace_id,
                    "traceparent": traceparent,
                    "finops": ledger.to_dict(),
                    "span_tree": span_tree,
                    **safr_panel_fields,
                }

                st.session_state.audit_log.append(
                    {
                        "case_id": payload.case_id,
                        "prompt": prompt,
                        "verdict_card": verdict_card,
                        "govops_panel": govops_panel,
                    }
                )

                st.markdown(summary)
                if not practitioner_view:
                    with st.expander("Deterministic Verdict Card"):
                        st.json(verdict_card)
                    with st.expander("Symbolic Proof Trace"):
                        deduction = verdict_card.get("symbolic_deduction")
                        if deduction:
                            for line in deduction["proof_trace"]:
                                st.code(line, language="prolog")
                        else:
                            st.write(
                                "No symbolic deduction executed (request denied at SAFR gate, or domain unmapped)."
                            )
                    with st.expander("GovOps & Telemetry Panel"):
                        st.json(govops_panel)

                st.session_state.messages.append(
                    {"role": "assistant", "content": summary, "verdict_card": verdict_card, "govops_panel": govops_panel}
                )

            except TokenBudgetExceededError as exc:
                error_message = f"🔴 FinOps circuit breaker tripped: {exc}"
                st.error(error_message)
                st.session_state.messages.append({"role": "assistant", "content": error_message})

st.divider()
approved = st.checkbox("I have reviewed the session output and approve it for the audit record (HITL sign-off)")
st.download_button(
    "Download Full Session Audit Log (JSON)",
    data=json.dumps(
        {
            "conversation_id": st.session_state.conversation_id,
            "enduser_id": enduser_id,
            "turns": st.session_state.audit_log,
        },
        indent=2,
        default=str,
    ),
    file_name=f"{st.session_state.conversation_id}_audit_log.json",
    mime="application/json",
    disabled=not approved or not st.session_state.audit_log,
)
