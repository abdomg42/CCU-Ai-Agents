"""Orchestrateur LangGraph du pipeline de diagnostic.

Graph :
    START -> intake -> collectors (logs/context/rag in parallel via asyncio.gather)
              -> root_cause -> remediation -> guardrail -> END
"""
import asyncio
import concurrent.futures
from typing import Any

from langgraph.graph import StateGraph, START, END

from shared.state import GraphState
from sub_agents.intake_parser.agent import run_intake
from sub_agents.logs_investigator.agent import run_logs
from sub_agents.context_agent.agent import run_context
from sub_agents.rag_ticket_search.agent import run_rag
from sub_agents.root_cause_reasoner.agent import run_root_cause
from sub_agents.remediation_planner.agent import run_remediation
from sub_agents.guardrail_validator.agent import run_guardrail


async def _collect_async(state: GraphState) -> dict[str, Any]:
    """Lance les trois agents collecteurs en parallèle avec asyncio.gather."""
    results = await asyncio.gather(
        asyncio.to_thread(run_logs, state),
        asyncio.to_thread(run_context, state),
        asyncio.to_thread(run_rag, state),
    )
    merged: dict[str, Any] = {}
    for r in results:
        merged.update(r)
    return merged


def _collect_sync(state: GraphState) -> dict[str, Any]:
    """Fallback synchrone parallèle avec ThreadPoolExecutor."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(run_logs, state),
            executor.submit(run_context, state),
            executor.submit(run_rag, state),
        ]
        merged: dict[str, Any] = {}
        for future in concurrent.futures.as_completed(futures):
            merged.update(future.result())
        return merged


def _collect(state: GraphState) -> dict[str, Any]:
    """Parallélisme : asyncio.gather par défaut, ThreadPoolExecutor si une boucle tourne déjà."""
    try:
        return asyncio.run(_collect_async(state))
    except RuntimeError:
        return _collect_sync(state)


class DiagnosticPipeline:
    def __init__(self) -> None:
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        builder = StateGraph(GraphState)

        builder.add_node("intake", run_intake)
        builder.add_node("collectors", _collect)
        builder.add_node("root_cause", run_root_cause)
        builder.add_node("remediation", run_remediation)
        builder.add_node("guardrail", run_guardrail)

        builder.add_edge(START, "intake")
        builder.add_edge("intake", "collectors")
        builder.add_edge("collectors", "root_cause")
        builder.add_edge("root_cause", "remediation")
        builder.add_edge("remediation", "guardrail")
        builder.add_edge("guardrail", END)

        return builder.compile()

    def run(self, incident: dict[str, Any]) -> dict[str, Any]:
        state = GraphState(incident=incident)
        final_state = self.graph.invoke(state)
        if isinstance(final_state, dict):
            return final_state
        return final_state.model_dump()


def run_diagnosis(incident: dict[str, Any]) -> dict[str, Any]:
    """Point d'entrée synchrone pour exécuter le diagnostic complet."""
    return DiagnosticPipeline().run(incident)
