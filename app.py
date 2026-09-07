"""Mega AI (Singapore Legal Control Plane) - Streamlit Control Plane UI.

Demonstrates a 4-stage neuro-symbolic pipeline:
  1. Neural Semantic Parsing  (core/neural_parser.py)
  2. Knowledge Graph Gate     (core/graph_gate.py)
  3. Symbolic Deduction       (core/symbolic_engine.py + core/procedural_calculators.py)
  4. Auditable HITL Export    (this file)
"""
from __future__ import annotations

import json
from datetime import date

import streamlit as st

from core.graph_gate import check_precedent_status
from core.neural_parser import parse_legal_case_text
from core.procedural_calculators import check_limitation_period
from core.symbolic_engine import run_symbolic_deduction

st.set_page_config(page_title="Mega AI - Singapore Legal Control Plane", layout="wide")

st.title("⚖️ Mega AI — Singapore Neuro-Symbolic Legal Control Plane")
st.caption(
    "Neural Semantic Parsing → Knowledge Graph Gate → Declarative Symbolic "
    "Deduction (pyDatalog) → Auditable HITL Export"
)

SAMPLE_TEXT = (
    "In this dispute, the loss was foreseeable and there was physical proximity "
    "between the parties. The defendant relies on an exemption clause in a "
    "standard form contract excluding liability for property damage. There was "
    "unequal bargaining power and no inducement was offered. The contract was "
    "breached on 2018-03-15. Cited precedent: Spandeck Engineering v AGC [2007] "
    "4 SLR(R) 100."
)

with st.sidebar:
    st.header("Input Stage")
    case_id = st.text_input("Case ID", value="case-001")
    case_text = st.text_area("Raw legal case text", value=SAMPLE_TEXT, height=260)
    breach_date_override = st.date_input(
        "Contract breach date (override, optional)",
        value=None,
        min_value=date(1960, 1, 1),
        max_value=date.today(),
    )
    run_clicked = st.button("Run Control Plane Pipeline", type="primary")

if not run_clicked:
    st.info("Configure the input in the sidebar and click **Run Control Plane Pipeline**.")
    st.stop()

# ---------------------------------------------------------------------------
# STAGE 1: NEURAL PARSING (semantic fact extraction only - no legal judgment)
# ---------------------------------------------------------------------------
st.header("Stage 1 — Neural Semantic Parsing")
payload = parse_legal_case_text(case_text, case_id=case_id)
if breach_date_override:
    payload.contract_breach_date = breach_date_override.isoformat()

st.json(payload.model_dump())

# ---------------------------------------------------------------------------
# STAGE 2: KNOWLEDGE GRAPH GATE (stare decisis precedent hierarchy)
# ---------------------------------------------------------------------------
st.header("Stage 2 — Knowledge Graph Gate (Stare Decisis)")
graph_result = check_precedent_status(payload.cited_precedent)

col1, col2 = st.columns(2)
with col1:
    st.metric("Precedent Status", graph_result["status"])
    st.metric("Good Law?", "Yes" if graph_result["is_good_law"] else "No")
with col2:
    st.write(f"**Citation:** {graph_result['citation']}")
    if graph_result["overruled_by"]:
        st.write(f"**Overruled by:** {graph_result['overruled_by']}")

if graph_result["warning"]:
    st.warning(graph_result["warning"])
else:
    st.success("Citation is good law. Proceeding to symbolic reasoning.")

# ---------------------------------------------------------------------------
# STAGE 3: SYMBOLIC REASONING (pyDatalog declarative deduction)
# ---------------------------------------------------------------------------
st.header("Stage 3 — Declarative Symbolic Deduction (pyDatalog)")
deduction = run_symbolic_deduction(payload)

col_a, col_b, col_c = st.columns(3)
with col_a:
    st.subheader("Spandeck Duty of Care")
    st.json(deduction["spandeck"])
with col_b:
    st.subheader("UCTA 1977")
    st.json(deduction["ucta"])
with col_c:
    st.subheader("Limitation Act 1959")
    if payload.contract_breach_date:
        limitation = check_limitation_period(payload.contract_breach_date)
        st.json(limitation)
    else:
        limitation = None
        st.info("No contract breach date extracted/provided.")

with st.expander("Symbolic Proof Trace"):
    for line in deduction["proof_trace"]:
        st.code(line, language="prolog")

# ---------------------------------------------------------------------------
# STAGE 4: AUDITABLE EXECUTION (Human-in-the-Loop export)
# ---------------------------------------------------------------------------
st.header("Stage 4 — Auditable Execution & HITL Export")
audit_log = {
    "case_id": payload.case_id,
    "neural_parsing_output": payload.model_dump(),
    "graph_gate_result": graph_result,
    "symbolic_deduction": deduction,
    "limitation_check": limitation,
}

approved = st.checkbox("I have reviewed this output and approve it for the case record (HITL sign-off)")
st.download_button(
    "Download Audit Log (JSON)",
    data=json.dumps(audit_log, indent=2, default=str),
    file_name=f"{payload.case_id}_audit_log.json",
    mime="application/json",
    disabled=not approved,
)
if approved:
    st.success("Audit log approved and ready for export.")
else:
    st.info("Review the pipeline output above, then check the approval box to enable export.")
