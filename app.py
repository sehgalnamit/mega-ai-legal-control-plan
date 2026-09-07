"""Mega AI (Singapore Legal Control Plane) - Real-Time Legal Chatbot.

Enforces the neuro-symbolic + GovOps architecture on every chat turn:
Neural Parsing -> Graph Gate -> MAS SAFR Envelope -> Symbolic Deduction
-> Procedural Calculator -> GovOps Telemetry (traces, FinOps, audit log).
"""
from __future__ import annotations

import json
import uuid

import streamlit as st

from core.govops.finops import (
    MAX_ITERATIONS_PER_CONVERSATION,
    FinOpsLedger,
    IterationCapExceededError,
    TokenBudgetExceededError,
    check_iteration_cap,
)
from core.govops.safr_envelope import SafrDisposition, evaluate_safr_envelope
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
from core.procedural_calculators import check_limitation_period
from core.response_renderer import render_legal_advice_summary
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

if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "iteration_count" not in st.session_state:
    st.session_state.iteration_count = 0
if "audit_log" not in st.session_state:
    st.session_state.audit_log = []

with st.sidebar:
    st.header("Session / GovOps Controls")
    enduser_id = st.text_input("enduser.id", value="lawyer_session_1")
    token_budget = st.number_input("FinOps token budget cap", min_value=1000, value=20_000, step=1000)
    st.caption(f"gen_ai.conversation.id: `{st.session_state.conversation_id}`")
    st.caption(f"Iterations: {st.session_state.iteration_count} / {MAX_ITERATIONS_PER_CONVERSATION}")
    if st.button("Reset conversation"):
        st.session_state.conversation_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.session_state.iteration_count = 0
        st.session_state.audit_log = []
        st.rerun()

st.title("⚖️ Mega AI — Singapore Legal Control Plane Chatbot")
st.caption(
    "Neuro-Symbolic pipeline with MAS SAFR governance, W3C trace propagation, and "
    "real-time FinOps cost tracking on every turn."
)

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("verdict_card"):
            with st.expander("Deterministic Verdict Card"):
                st.json(message["verdict_card"])
        if message.get("govops_panel"):
            with st.expander("GovOps & Telemetry Panel"):
                st.json(message["govops_panel"])

prompt = st.chat_input("Describe the dispute (e.g. the aircon maintenance scenario)...")

if not st.session_state.messages and not prompt:
    st.info("💡 Try the sample aircon maintenance dispute, or type your own scenario in the chat box below.")
    if st.button("Use sample aircon dispute"):
        prompt = AIRCON_DISPUTE_SAMPLE

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

                with start_worker_span("graph_gate", "execute_tool", "graph_gate"):
                    graph_result = check_precedent_status(payload.cited_precedent)

                safr_result = evaluate_safr_envelope(
                    payload,
                    extraction_confidence=payload.extraction_confidence,
                    claim_value_usd=payload.claim_value_sgd,
                )
                set_disposition(root_span, safr_result.verdict)

                deduction = None
                limitation = None
                if safr_result.disposition != SafrDisposition.DENY:
                    with start_worker_span("symbolic_deduction", "execute_tool", "symbolic_engine"):
                        deduction = run_symbolic_deduction(payload)

                    if payload.contract_breach_date:
                        with start_worker_span(
                            "limitation_calculator", "execute_tool", "procedural_calculator"
                        ):
                            limitation = check_limitation_period(payload.contract_breach_date)

            spans = get_captured_spans()
            span_tree = build_span_tree(spans)
            trace_id = span_tree[0]["trace_id"] if span_tree else None

            if safr_result.disposition == SafrDisposition.DENY:
                summary = "🚫 This request was **denied** by the MAS SAFR governance envelope: " + "; ".join(
                    safr_result.reasons
                )
            else:
                summary = render_legal_advice_summary(payload, deduction, limitation, graph_result)
                if safr_result.disposition == SafrDisposition.ESCALATE:
                    summary = "🧑‍⚖️ **Escalated for human-in-the-loop review.** " + summary

            verdict_card = {
                "case_id": payload.case_id,
                "extracted_facts": payload.model_dump(),
                "graph_gate": graph_result,
                "symbolic_deduction": deduction,
                "limitation_check": limitation,
            }
            govops_panel = {
                "trace_id": trace_id,
                "traceparent": traceparent,
                "safr_disposition": safr_result.disposition.value,
                "safr_verdict": safr_result.verdict,
                "safr_reasons": safr_result.reasons,
                "finops": ledger.to_dict(),
                "span_tree": span_tree,
            }

            st.session_state.audit_log.append(
                {"case_id": payload.case_id, "prompt": prompt, "verdict_card": verdict_card, "govops_panel": govops_panel}
            )

            st.markdown(summary)
            with st.expander("Deterministic Verdict Card"):
                st.json(verdict_card)
            with st.expander("Symbolic Proof Trace"):
                if deduction:
                    for line in deduction["proof_trace"]:
                        st.code(line, language="prolog")
                else:
                    st.write("No symbolic deduction executed (request denied at SAFR gate).")
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
