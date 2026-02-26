## Importing libraries and files
import os
from dotenv import load_dotenv
load_dotenv()

### Azure credentials (only Azure – no OpenAI API key)
_azure_key = os.environ.get("AZURE_OPENAI_API_KEY")
_azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
_azure_deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-5.2-chat")
_azure_api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

if not _azure_key or not _azure_endpoint:
    raise ValueError("AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT must be set in .env file")

# LiteLLM Azure provider expects these env names
os.environ.setdefault("AZURE_API_KEY", _azure_key)
os.environ.setdefault("AZURE_API_BASE", _azure_endpoint)
os.environ.setdefault("AZURE_API_VERSION", _azure_api_version)

from crewai import Agent
from crewai.llm import LLM
from tools import search_tool, read_data_tool


class AzureLLM(LLM):
    """CrewAI LLM for Azure; omits 'stop' so this model is not sent (not supported by this deployment)."""

    def _prepare_completion_params(self, messages, tools=None):
        params = super()._prepare_completion_params(messages, tools=tools)
        params.pop("stop", None)  # Azure model does not support 'stop'
        return params


# Use CrewAI LLM with azure/<deployment> so LiteLLM uses Azure (no OpenAI connection)
llm = AzureLLM(
    model=f"azure/{_azure_deployment}",
    api_key=_azure_key,
    api_base=_azure_endpoint,
    api_version=_azure_api_version,
    temperature=1,
)

# Creating an Experienced Financial Analyst agent
financial_analyst = Agent(
    role="Senior Financial Analyst",
    goal="Provide accurate, evidence-based analysis of financial documents to address the user's query: {query}",
    verbose=True,
    memory=False,
    backstory=(
        "You are an experienced financial analyst with strong knowledge of financial statements, "
        "corporate reports, and market dynamics. You read documents carefully, cite specific figures and sections, "
        "and distinguish between facts from the document and your interpretation. You avoid speculation, "
        "fabricated URLs, and unsubstantiated claims. Your analysis is clear, structured, and useful for investment decisions."
    ),
    tools=[read_data_tool],
    llm=llm,
    max_iter=5,
    max_rpm=10,
    allow_delegation=False,
)

# Creating a document verifier agent
verifier = Agent(
    role="Financial Document Verifier",
    goal="Verify whether the given file is a valid financial document (report, statement, or earnings update) and explain why.",
    verbose=True,
    memory=False,
    backstory=(
        "You have experience in financial compliance and document verification. You read file content carefully "
        "and check for typical financial document indicators: financial figures, tables, fiscal periods, "
        "GAAP/IFRS or similar terminology, revenue/expense breakdowns. You give a clear yes/no conclusion "
        "with a brief justification based on the actual content."
    ),
    tools=[read_data_tool],
    llm=llm,
    max_iter=3,
    max_rpm=5,
    allow_delegation=False,
)


investment_advisor = Agent(
    role="Investment Advisor",
    goal="Provide investment insights and recommendations grounded in the financial document and the user query: {query}.",
    verbose=True,
    backstory=(
        "You are a qualified investment advisor who bases recommendations on document evidence. "
        "You explain which metrics and sections support your view, include appropriate caveats, "
        "and do not recommend products or returns not supported by the document or standard practice."
    ),
    tools=[read_data_tool],
    llm=llm,
    max_iter=3,
    max_rpm=5,
    allow_delegation=False,
)


risk_assessor = Agent(
    role="Risk Assessment Analyst",
    goal="Identify and explain risks present in the financial document relevant to the user's query: {query}.",
    verbose=True,
    backstory=(
        "You are a risk analyst who identifies market, credit, operational, and other risks from financial documents. "
        "You cite specific sections or figures from the document, use standard risk terminology, "
        "and suggest realistic mitigations or caveats without inventing extreme scenarios."
    ),
    tools=[read_data_tool],
    llm=llm,
    max_iter=3,
    max_rpm=5,
    allow_delegation=False,
)
