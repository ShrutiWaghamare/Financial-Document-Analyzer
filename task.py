from crewai import Task
from agents import financial_analyst, verifier, investment_advisor, risk_assessor
from tools import read_data_tool

# Step 1: Verify the document first
verification = Task(
    description=(
        "Verify whether the file at {file_path} is a valid financial document "
        "(e.g. report, statement, earnings update).\n"
        "Use read_data_tool with path '{file_path}' to inspect the content. "
        "Check for financial figures, tables, fiscal periods, GAAP/IFRS terms.\n"
        "Respond with a clear yes/no and a short justification based on actual content."
    ),
    expected_output=(
        "A short verification result: yes or no, with 1–2 sentences of justification "
        "based on the document content."
    ),
    agent=verifier,
    tools=[read_data_tool],
    async_execution=False,
)

# Step 2: Core financial analysis
analyze_financial_document = Task(
    description=(
        "Analyze the financial document at {file_path} to address: {query}.\n"
        "Use read_data_tool with path '{file_path}' to load the document.\n"
        "Provide evidence-based analysis: key figures, trends, risks, and implications.\n"
        "Base your response only on the document. Do not speculate or invent sources."
    ),
    expected_output=(
        "A structured analysis including:\n"
        "- Summary of the document and key figures\n"
        "- Relevant risks and opportunities\n"
        "- Investment-related insights grounded in the document\n"
        "- Professional language without fabricated sources"
    ),
    agent=financial_analyst,
    tools=[read_data_tool],
    context=[verification],       # builds on verification result
    async_execution=False,
)

# Step 3: Investment advice grounded in the analysis
investment_analysis = Task(
    description=(
        "Using findings from the financial analysis of {file_path}, provide investment "
        "insights for: {query}.\n"
        "You may use read_data_tool if you need to re-check specific figures.\n"
        "Tie every recommendation to metrics from the document. "
        "Include caveats and avoid unsupported claims."
    ),
    expected_output=(
        "Structured investment analysis:\n"
        "- Key metrics from the document relevant to the query\n"
        "- Recommendations tied to those metrics\n"
        "- Clear caveats and cited data sources"
    ),
    agent=investment_advisor,      # ← correct specialized agent
    tools=[read_data_tool],
    context=[analyze_financial_document],  # builds on analyst findings
    async_execution=False,
)

# Step 4: Risk assessment grounded in the analysis
risk_assessment = Task(
    description=(
        "Using findings from the financial analysis of {file_path}, produce a risk "
        "assessment relevant to: {query}.\n"
        "You may use read_data_tool to verify specific figures.\n"
        "Only identify risks actually stated or implied in the document. "
        "Use standard risk terminology (market, credit, operational, liquidity, etc.)."
    ),
    expected_output=(
        "Structured risk assessment:\n"
        "- Risks identified from the document with supporting evidence\n"
        "- Risk category labels (market, credit, operational, etc.)\n"
        "- Realistic mitigations or caveats"
    ),
    agent=risk_assessor,           # ← correct specialized agent
    tools=[read_data_tool],
    context=[analyze_financial_document],  # builds on analyst findings
    async_execution=False,
)