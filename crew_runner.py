"""
CrewAI orchestration: run_crew and helpers.

Standard approach:
  1. Read PDF content in Python (tools.py) — NOT via LLM tool call
  2. Pass content directly to agents via {document_content}
  3. Agents analyze text — no file path handling by LLM at all
"""
import os
import logging

from crewai import Crew, Process

from agents import financial_analyst, verifier, investment_advisor, risk_assessor
from task import (
    verification,
    analyze_financial_document,
    investment_analysis,
    risk_assessment,
)
from tools import read_pdf_content

logger   = logging.getLogger(__name__)
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def _get_pdf_from_data_folder() -> str | None:
    """Return absolute path to first PDF in data folder, or None."""
    if not os.path.isdir(DATA_DIR):
        return None
    for name in sorted(os.listdir(DATA_DIR)):
        if name.lower().endswith(".pdf"):
            return os.path.abspath(os.path.join(DATA_DIR, name))
    return None


def run_crew(query: str, file_path: str | None = None) -> str:
    """
    1. Resolve file path
    2. Read PDF content in Python (no LLM path handling)
    3. Select agents based on query keywords
    4. Pass content directly to agents via {document_content}
    """
    # ── Step 1: Resolve file path ──────────────────────────────────────────────
    if file_path is None:
        file_path = _get_pdf_from_data_folder()

    if not file_path:
        raise FileNotFoundError(
            "No PDF found. Add a PDF to data/ or upload via /analyze."
        )

    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"PDF not found at: {file_path}")

    query = query.strip() or "Analyze this financial document for investment insights"

    # ── Step 2: Read PDF in Python ─────────────────────────────────────────────
    logger.warning(f"[crew_runner] Reading PDF: {os.path.basename(file_path)}")
    document_content = read_pdf_content(file_path)
    logger.warning(f"[crew_runner] Content extracted: {len(document_content)} chars")

    if document_content.startswith("Error:"):
        raise ValueError(f"Could not read PDF: {document_content}")

    # ── Step 3: Select agents based on query keywords ─────────────────────────
    query_lower = query.lower()

    selected_agents = [verifier]
    selected_tasks  = [verification]

    if any(w in query_lower for w in [
        "analyze", "analysis", "summary", "overview",
        "figures", "performance", "revenue", "profit"
    ]):
        selected_agents.append(financial_analyst)
        selected_tasks.append(analyze_financial_document)

    if any(w in query_lower for w in [
        "invest", "buy", "sell", "recommendation",
        "portfolio", "return", "valuation", "insight"
    ]):
        selected_agents.append(investment_advisor)
        selected_tasks.append(investment_analysis)

    if any(w in query_lower for w in [
        "risk", "threat", "downside", "concern",
        "exposure", "volatility", "loss"
    ]):
        selected_agents.append(risk_assessor)
        selected_tasks.append(risk_assessment)

    # Fallback: run all agents if no keywords matched
    if len(selected_tasks) == 1:
        selected_agents = [verifier, financial_analyst, investment_advisor, risk_assessor]
        selected_tasks  = [verification, analyze_financial_document, investment_analysis, risk_assessment]

    agent_names = [a.role for a in selected_agents]
    logger.warning(f"[crew_runner] Running agents: {agent_names}")

    # ── Step 4: Run crew with content injected directly ───────────────────────
    crew = Crew(
        agents   = selected_agents,
        tasks    = selected_tasks,
        process  = Process.sequential,
        verbose  = False,   # ← no crew-level output to terminal
    )

    result = crew.kickoff({
        "query"            : query,
        "document_content" : document_content,
    })

    logger.warning(f"[crew_runner] Done. Result length: {len(str(result))} chars")
    return str(result)