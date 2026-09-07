"""Knowledge Graph Gate: precedent hierarchy and stare decisis filtering.

The graph is CONTEXT, not reasoning: it never decides a legal outcome.
Its only job is to tell the rest of the pipeline whether a cited
precedent is still good law, so that overruled judgments are pruned
from the context *before* fact extraction / symbolic deduction runs.

Uses a NetworkX in-memory graph as a lightweight, dependency-free
fallback for a real Neo4j deployment (same data model, swappable
backend).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Optional

import networkx as nx


class CourtLevel(IntEnum):
    """Singapore court hierarchy, ordered by binding authority."""

    STATE_COURTS = 1
    SGHC = 2
    SGCA = 3


class PrecedentOverruledWarning(Warning):
    """Raised when a cited precedent has been overruled by a higher court."""


@dataclass
class PrecedentNode:
    citation: str
    court: CourtLevel
    status: str = "GOOD_LAW"


class PrecedentGraph:
    """Simulates a Neo4j precedent hierarchy graph using NetworkX."""

    def __init__(self) -> None:
        self.graph = nx.DiGraph()
        self._seed_demo_precedents()

    def _seed_demo_precedents(self) -> None:
        self.add_precedent("Spandeck Engineering v AGC [2007] 4 SLR(R) 100", CourtLevel.SGCA)
        self.add_precedent("Anns v Merton [1978] AC 728 (Sing. adoption)", CourtLevel.SGHC)
        self.add_precedent(
            "RDC Concrete Pte Ltd v Sato Kogyo (S) Pte Ltd [2007] 4 SLR(R) 413", CourtLevel.SGCA
        )
        self.add_precedent("Old State Courts Ruling on Duty of Care", CourtLevel.STATE_COURTS)
        self.overrule(
            "Old State Courts Ruling on Duty of Care",
            "Spandeck Engineering v AGC [2007] 4 SLR(R) 100",
        )

    def add_precedent(self, citation: str, court: CourtLevel) -> None:
        self.graph.add_node(citation, court=court, status="GOOD_LAW")

    def overrule(self, overruled_citation: str, overruled_by_citation: str) -> None:
        if overruled_citation not in self.graph:
            self.add_precedent(overruled_citation, CourtLevel.STATE_COURTS)
        self.graph.nodes[overruled_citation]["status"] = "OVERRULED"
        self.graph.add_edge(overruled_citation, overruled_by_citation, relation="OVERRULED_BY")

    def check_precedent_status(self, case_citation: str) -> dict:
        """Return good-law status for a citation, pruning it if overruled."""
        if case_citation not in self.graph:
            return {
                "citation": case_citation,
                "status": "UNKNOWN",
                "is_good_law": True,
                "overruled_by": None,
                "warning": None,
            }

        node = self.graph.nodes[case_citation]
        status = node.get("status", "GOOD_LAW")
        overruled_by = None
        warning = None

        if status == "OVERRULED":
            successors = list(self.graph.successors(case_citation))
            overruled_by = successors[0] if successors else None
            warning = (
                f"PrecedentOverruledWarning: '{case_citation}' has been overruled "
                f"by '{overruled_by}'. Pruning from reasoning context."
            )

        return {
            "citation": case_citation,
            "status": status,
            "is_good_law": status != "OVERRULED",
            "overruled_by": overruled_by,
            "warning": warning,
        }


_DEFAULT_GRAPH = PrecedentGraph()


def check_precedent_status(case_citation: str, graph: Optional[PrecedentGraph] = None) -> dict:
    """Module-level convenience wrapper using a shared demo graph instance."""
    graph = graph or _DEFAULT_GRAPH
    return graph.check_precedent_status(case_citation)
