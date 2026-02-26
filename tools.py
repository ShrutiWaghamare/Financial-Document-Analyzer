## Importing libraries and files
import os
from dotenv import load_dotenv
load_dotenv()

from crewai.tools import tool
from langchain_community.document_loaders import PyPDFLoader

try:
    from crewai_tools.tools.serper_dev_tool.serper_dev_tool import SerperDevTool
    search_tool = SerperDevTool()
except Exception:
    search_tool = None  # optional: set SERPER_API_KEY to enable web search



@tool("Read financial document from PDF")
def read_data_tool(path: str) -> str:
    """Read content from a PDF file at the given path. Use this to load the financial document before analyzing. Returns the full text of the document.

    Args:
        path: Full path to the PDF file (e.g. data/sample.pdf or the path provided in the task).

    Returns:
        Full text content of the financial document.
    """
    if not path or not path.strip():
        return "Error: No file path provided."
    path = path.strip()
    if not os.path.exists(path):
        return f"Error: File not found at path: {path}"
    try:
        loader = PyPDFLoader(path)
        docs = loader.load()
    except Exception as e:
        return f"Error loading PDF: {str(e)}"
    full_report = ""
    for data in docs:
        content = data.page_content
        while "\n\n" in content:
            content = content.replace("\n\n", "\n")
        full_report += content + "\n"
    return full_report or "No text could be extracted from the PDF."

## Creating Investment Analysis Tool
class InvestmentTool:
    def analyze_investment_tool(self, financial_document_data: str) -> str:
        processed_data = financial_document_data or ""
        i = 0
        while i < len(processed_data):
            if processed_data[i : i + 2] == "  ":
                processed_data = processed_data[:i] + processed_data[i + 1 :]
            else:
                i += 1
        return "Investment analysis functionality to be implemented"


## Creating Risk Assessment Tool
class RiskTool:
    def create_risk_assessment_tool(self, financial_document_data: str) -> str:
        return "Risk assessment functionality to be implemented"