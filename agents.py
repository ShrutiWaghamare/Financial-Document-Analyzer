import os
from dotenv import load_dotenv
load_dotenv()

_azure_key         = os.environ.get("AZURE_OPENAI_API_KEY")
_azure_endpoint    = os.environ.get("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
_azure_deployment  = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-5.2-chat")
_azure_api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

if not _azure_key or not _azure_endpoint:
    raise ValueError("AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT must be set in .env file")

os.environ.setdefault("AZURE_API_KEY",     _azure_key)
os.environ.setdefault("AZURE_API_BASE",    _azure_endpoint)
os.environ.setdefault("AZURE_API_VERSION", _azure_api_version)

from crewai import Agent
from crewai.llm import LLM


class AzureLLM(LLM):
    """CrewAI LLM wrapper for Azure — omits 'stop' param (not supported)."""
    def _prepare_completion_params(self, messages, tools=None):
        params = super()._prepare_completion_params(messages, tools=tools)
        params.pop("stop", None)
        return params


llm = AzureLLM(
    model       = f"azure/{_azure_deployment}",
    api_key     = _azure_key,
    api_base    = _azure_endpoint,
    api_version = _azure_api_version,
    temperature = 1,
)

# ── verbose=False on all agents ────────────────────────────────────────────────
# Terminal will stay clean. Final results are always saved to DB and returned
# via GET /result/{job_id} regardless of verbose setting.

financial_analyst = Agent(
    role      = "Senior Financial Analyst",
    goal      = "Provide accurate, evidence-based analysis of the financial document content to address: {query}",
    verbose   = False,   # ← no agent thinking printed to terminal
    memory    = False,
    backstory = (
        "You are an experienced financial analyst with deep knowledge of financial statements, "
        "corporate reports, and market dynamics. You read document content carefully, cite specific "
        "figures and sections, and distinguish between facts and interpretation. "
        "You never speculate or fabricate numbers. Your analysis is clear, structured, "
        "and directly tied to the document content provided to you."
    ),
    llm              = llm,
    max_iter         = 3,
    max_rpm          = 10,
    allow_delegation = False,
)

verifier = Agent(
    role      = "Financial Document Verifier",
    goal      = "Verify whether the given document content is a valid financial document and explain why.",
    verbose   = False,
    memory    = False,
    backstory = (
        "You have experience in financial compliance and document verification. "
        "You read document content carefully and check for typical financial indicators: "
        "financial figures, tables, fiscal periods, GAAP/IFRS terminology, "
        "revenue/expense breakdowns. You give a clear yes/no conclusion with brief justification."
    ),
    llm              = llm,
    max_iter         = 2,
    max_rpm          = 5,
    allow_delegation = False,
)

investment_advisor = Agent(
    role      = "Investment Advisor",
    goal      = "Provide investment insights and recommendations grounded in the document content for: {query}",
    verbose   = False,
    memory    = False,
    backstory = (
        "You are a qualified investment advisor who bases recommendations strictly on document evidence. "
        "You explain which metrics and sections support your view, include appropriate caveats, "
        "and never recommend products or cite returns not supported by the document."
    ),
    llm              = llm,
    max_iter         = 3,
    max_rpm          = 5,
    allow_delegation = False,
)

risk_assessor = Agent(
    role      = "Risk Assessment Analyst",
    goal      = "Identify and explain risks from the document content relevant to: {query}",
    verbose   = False,
    memory    = False,
    backstory = (
        "You are a risk analyst who identifies market, credit, operational, and liquidity risks "
        "strictly from document content. You cite specific figures, use standard risk terminology, "
        "and suggest realistic mitigations without inventing extreme scenarios."
    ),
    llm              = llm,
    max_iter         = 3,
    max_rpm          = 5,
    allow_delegation = False,
)