"""Orchestrateur LangGraph du pipeline de diagnostic.

Graph :
    START -> intake -> collectors (logs/context/rag in parallel)
              -> root_cause -> ticket_manager -> remediation_explainer
              -> content_guardrail -> report_generator -> notifier -> END

L'agent n'exécute JAMAIS d'action technique : il se contente d'informer,
de diagnostiquer, de rapporter et de notifier.
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
from sub_agents.ticket_manager.agent import run_ticket_manager
from sub_agents.remediation_explainer.agent import run_remediation_explanation
from sub_agents.content_guardrail.pii_sanitizer import run_content_guardrail
from sub_agents.report_generator.agent import run_report_generator
from sub_agents.notifier.agent import run_notifier


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
        builder.add_node("ticket_manager", run_ticket_manager)
        builder.add_node("remediation_explainer", run_remediation_explanation)
        builder.add_node("content_guardrail", run_content_guardrail)
        builder.add_node("report_generator", run_report_generator)
        builder.add_node("notifier", run_notifier)

        builder.add_edge(START, "intake")
        builder.add_edge("intake", "collectors")
        builder.add_edge("collectors", "root_cause")
        builder.add_edge("root_cause", "ticket_manager")
        builder.add_edge("ticket_manager", "remediation_explainer")
        builder.add_edge("remediation_explainer", "content_guardrail")
        builder.add_edge("content_guardrail", "report_generator")
        builder.add_edge("report_generator", "notifier")
        builder.add_edge("notifier", END)

        return builder.compile()

    def run(self, incident: dict[str, Any]) -> dict[str, Any]:
        state = GraphState(incident=incident)
        final_state = self.graph.invoke(state)
        if isinstance(final_state, dict):
            return final_state
        return final_state.model_dump()

    def stream(self, incident: dict[str, Any]):
        """Génère les mises à jour de chaque nœud du graphe (stream_mode='updates')."""
        state = GraphState(incident=incident)
        yield from self.graph.stream(state, stream_mode="updates")


def run_diagnosis(incident: dict[str, Any]) -> dict[str, Any]:
    """Point d'entrée synchrone pour exécuter le diagnostic complet."""
    return DiagnosticPipeline().run(incident)


def stream_diagnosis(incident: dict[str, Any]):
    """Point d'entrée de streaming pour le diagnostic."""
    yield from DiagnosticPipeline().stream(incident)
