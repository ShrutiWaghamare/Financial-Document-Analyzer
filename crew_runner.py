"""
CrewAI orchestration: run_crew and helpers.
Separate module so worker can import run_crew without circular dependency on main.
"""
import os

from crewai import Crew, Process

from agents import financial_analyst, verifier, investment_advisor, risk_assessor
from task import (
    verification,
    analyze_financial_document,
    investment_analysis,
    risk_assessment,
)

DATA_DIR = "data"


def _get_pdf_from_data_folder() -> str | None:
    """Return path to first PDF in data folder, or None if none found."""
    if not os.path.isdir(DATA_DIR):
        return None
    for name in sorted(os.listdir(DATA_DIR)):
        if name.lower().endswith(".pdf"):
            return os.path.join(DATA_DIR, name)
    return None


def run_crew(query: str, file_path: str | None = None):
    """
    Run CrewAI agents based on query intent. Always runs verifier first.
    If file_path is None, uses first PDF in data/.
    """
    if file_path is None:
        file_path = _get_pdf_from_data_folder()
    if not file_path or not os.path.isfile(file_path):
        raise FileNotFoundError(
            "No PDF found in data folder. Add a PDF to data/ or upload via /analyze."
        )

    query_lower = query.lower().strip()
    query = query.strip() or "Analyze this financial document for investment insights"

    selected_agents = [verifier]
    selected_tasks = [verification]

    if any(
        w in query_lower
        for w in [
            "analyze",
            "summary",
            "overview",
            "figures",
            "performance",
        ]
    ):
        selected_agents.append(financial_analyst)
        selected_tasks.append(analyze_financial_document)

    if any(
        w in query_lower
        for w in ["invest", "buy", "sell", "recommendation", "portfolio"]
    ):
        selected_agents.append(investment_advisor)
        selected_tasks.append(investment_analysis)

    if any(
        w in query_lower
        for w in ["risk", "threat", "downside", "concern", "exposure"]
    ):
        selected_agents.append(risk_assessor)
        selected_tasks.append(risk_assessment)

    # If no keywords matched, only verifier runs (faster). Use keywords above to add more agents.
    crew = Crew(
        agents=selected_agents,
        tasks=selected_tasks,
        process=Process.sequential,
    )
    result = crew.kickoff({"query": query, "file_path": file_path})
    return result
