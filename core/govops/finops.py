"""FinOps token accounting and circuit-breaker / iteration-cap guardrails.

Tracks input/output/cached tokens per pipeline step, computes live
cumulative $USD cost, and trips a circuit breaker before a runaway
loop can drain the token budget - the joint FinOps + resilience
control described in the GovOps operations model.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

# Iteration cap: hard bound on inter-turn/agent hops per conversation to
# prevent unbounded recursive delegation loops.
MAX_ITERATIONS_PER_CONVERSATION = 20

# USD per 1,000 tokens. Illustrative rates - update to match negotiated
# enterprise pricing before relying on this for real budgeting.
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    "gpt-4o": {"input": 0.0025, "output": 0.010},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "claude-3-5-sonnet-20241022": {"input": 0.003, "output": 0.015},
    "mock-offline-parser": {"input": 0.0, "output": 0.0},
}
_DEFAULT_MODEL_RATE = {"input": 0.0005, "output": 0.0015}


class TokenBudgetExceededError(Exception):
    """Raised when cumulative token usage would exceed the circuit-breaker budget."""


class IterationCapExceededError(Exception):
    """Raised when a conversation exceeds the max allowed orchestration iterations."""


def check_iteration_cap(current_iteration: int, max_iterations: int = MAX_ITERATIONS_PER_CONVERSATION) -> None:
    if current_iteration >= max_iterations:
        raise IterationCapExceededError(
            f"[Iteration Cap TRIPPED]: conversation reached {current_iteration}/{max_iterations} "
            "turns. Start a new conversation or escalate for human review."
        )


@dataclass
class TokenUsageRecord:
    step_name: str
    model: str
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int = 0
    cost_usd: float = 0.0


@dataclass
class FinOpsLedger:
    """Per-request token/cost ledger enforcing a circuit-breaker budget."""

    max_token_budget: int = 20_000
    records: List[TokenUsageRecord] = field(default_factory=list)
    consumed_tokens: int = 0

    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        rates = MODEL_PRICING.get(model, _DEFAULT_MODEL_RATE)
        cost = (input_tokens / 1000.0) * rates["input"] + (output_tokens / 1000.0) * rates["output"]
        return round(cost, 6)

    def record(
        self,
        step_name: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cached_input_tokens: int = 0,
    ) -> TokenUsageRecord:
        """Track a step's token usage; trips the circuit breaker if the
        cumulative request budget would be exceeded.
        """
        total_step_tokens = input_tokens + output_tokens
        if self.consumed_tokens + total_step_tokens > self.max_token_budget:
            raise TokenBudgetExceededError(
                f"[Circuit Breaker TRIPPED]: {self.consumed_tokens + total_step_tokens} "
                f"tokens would exceed budget ({self.max_token_budget}) at step '{step_name}'."
            )

        cost = self.calculate_cost(model, input_tokens, output_tokens)
        record = TokenUsageRecord(
            step_name=step_name,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_input_tokens=cached_input_tokens,
            cost_usd=cost,
        )
        self.records.append(record)
        self.consumed_tokens += total_step_tokens
        return record

    @property
    def total_cost_usd(self) -> float:
        return round(sum(r.cost_usd for r in self.records), 6)

    @property
    def budget_remaining(self) -> int:
        return max(self.max_token_budget - self.consumed_tokens, 0)

    def to_dict(self) -> Dict[str, object]:
        return {
            "records": [vars(r) for r in self.records],
            "total_input_tokens": sum(r.input_tokens for r in self.records),
            "total_output_tokens": sum(r.output_tokens for r in self.records),
            "total_cost_usd": self.total_cost_usd,
            "max_token_budget": self.max_token_budget,
            "budget_remaining": self.budget_remaining,
        }
