"""AI assistant service layer."""

from typing import Any, List
from dotenv import load_dotenv

load_dotenv()

from langchain_core.messages import HumanMessage

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError:  # pragma: no cover - optional dependency guard
    ChatGoogleGenerativeAI = None

#llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0) if ChatGoogleGenerativeAI else None


def ask_agent(question: str, df: Any, history: List[Any]) -> str:
#     if llm is None:
#         return "AI service is unavailable because the required package is not installed."

#     context = df.to_json(orient="records", indent=2)

#     conversation = ""
#     for msg in history:
#         if isinstance(msg, HumanMessage):
#             conversation += f"User: {msg.content}\n"
#         else:
#             conversation += f"Assistant: {msg.content}\n"

#     prompt = f"""
# You are an Azure DevOps QA Assistant.

# Below is the current execution data.

# {context}

# Conversation History:

# {conversation}

# Answer ONLY using the execution data.

# If information is unavailable, say "Not available."

# Current User Question:
# {question}
# """

    #response = llm.invoke([HumanMessage(content=prompt)])
    return "Yes AI serice working" 
