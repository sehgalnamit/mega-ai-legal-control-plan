"""OpenTelemetry distributed tracing with W3C trace-context propagation.

Every legal chat request gets a root span (`gen_ai.operation.name =
"legal_chat_request"`) and each pipeline worker step (neural parser,
graph gate, symbolic engine, procedural calculator) gets a child span.
Spans are captured in-memory so the Streamlit UI can render a span
tree without needing an external OTLP collector; set the standard
`OTEL_EXPORTER_OTLP_ENDPOINT` env var to additionally export to a real
collector (e.g. Dynatrace, an OTel Collector).
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional

from opentelemetry import baggage, context, trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.trace import SpanKind, Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

_propagator = TraceContextTextMapPropagator()


class InMemorySpanExporter(SpanExporter):
    """Captures finished spans in memory for the GovOps telemetry panel."""

    def __init__(self) -> None:
        self.spans: List[ReadableSpan] = []

    def export(self, spans) -> SpanExportResult:
        self.spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        pass

    def clear(self) -> None:
        self.spans.clear()


_exporter = InMemorySpanExporter()
_provider = TracerProvider(resource=Resource.create({"service.name": "mega-ai-legal-control-plane"}))
_provider.add_span_processor(SimpleSpanProcessor(_exporter))

_otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
if _otlp_endpoint:
    # Optional real collector export (e.g. Dynatrace, an OTel Collector).
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    headers_raw = os.getenv("OTEL_EXPORTER_OTLP_HEADERS", "")
    headers = dict(item.split("=", 1) for item in headers_raw.split(",") if "=" in item)
    _provider.add_span_processor(
        SimpleSpanProcessor(OTLPSpanExporter(endpoint=_otlp_endpoint, headers=headers or None))
    )

trace.set_tracer_provider(_provider)
tracer = trace.get_tracer("mega_ai.legal_control_plane", "1.0.0")


def reset_trace_buffer() -> None:
    """Clear captured spans before starting a new chat turn."""
    _exporter.clear()


def get_captured_spans() -> List[ReadableSpan]:
    return list(_exporter.spans)


def inject_traceparent() -> Dict[str, str]:
    """Return the current W3C `traceparent` header for downstream propagation."""
    carrier: Dict[str, str] = {}
    _propagator.inject(carrier)
    return carrier


@contextmanager
def start_root_span(conversation_id: str, enduser_id: str, user_query: str) -> Iterator[trace.Span]:
    """Root span for a legal chat request.

    Attaches the mandatory `gen_ai.conversation.id` / `enduser.id`
    baggage attributes so they propagate to every downstream worker span.
    """
    ctx = baggage.set_baggage("gen_ai.conversation.id", conversation_id)
    ctx = baggage.set_baggage("enduser.id", enduser_id, context=ctx)
    token = context.attach(ctx)
    try:
        with tracer.start_as_current_span("legal_chat_request", kind=SpanKind.SERVER) as span:
            span.set_attribute("gen_ai.operation.name", "legal_chat_request")
            span.set_attribute("gen_ai.conversation.id", conversation_id)
            span.set_attribute("enduser.id", enduser_id)
            span.set_attribute("gen_ai.content.prompt", user_query[:2000])
            yield span
    finally:
        context.detach(token)


@contextmanager
def start_worker_span(
    name: str,
    operation_name: str,
    agent_name: str,
    **attributes: Any,
) -> Iterator[trace.Span]:
    """Child span for a single worker step (neural parser, graph gate,
    symbolic engine, procedural calculator), nested under the current
    root span's W3C trace context.
    """
    with tracer.start_as_current_span(name, kind=SpanKind.INTERNAL) as span:
        span.set_attribute("gen_ai.operation.name", operation_name)
        span.set_attribute("gen_ai.agent.name", agent_name)
        for key, value in attributes.items():
            if value is not None:
                span.set_attribute(key, value)
        try:
            yield span
            span.set_status(Status(StatusCode.OK))
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            raise


def set_disposition(span: trace.Span, verdict: str) -> None:
    """Attach the mandatory `safr.disposition.verdict` (ALLOW/DENY/ESCALATE)."""
    span.set_attribute("safr.disposition.verdict", verdict)


def build_span_tree(spans: List[ReadableSpan]) -> List[Dict[str, Any]]:
    """Flatten captured spans into rows for the GovOps span-tree table."""
    rows = []
    for s in spans:
        ctx = s.get_span_context()
        rows.append(
            {
                "name": s.name,
                "trace_id": format(ctx.trace_id, "032x"),
                "span_id": format(ctx.span_id, "016x"),
                "parent_span_id": format(s.parent.span_id, "016x") if s.parent else None,
                "duration_ms": (
                    round((s.end_time - s.start_time) / 1_000_000, 3) if s.end_time and s.start_time else None
                ),
                "status": s.status.status_code.name,
                "attributes": dict(s.attributes or {}),
            }
        )
    return rows
