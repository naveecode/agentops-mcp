"""Tool-calling agent.

Uses a LangGraph ReAct agent when OPENAI_API_KEY is set. Otherwise a
deterministic router picks calculator or search_docs so tests and demos
run offline. Guardrails run before either path.
"""
import os
import re

from .guardrails import refusal
from .tools import TOOLS

_ARITHMETIC = re.compile(r"[\d\s+\-*/().^]+")


def route(question: str) -> tuple[str, dict]:
    if _ARITHMETIC.fullmatch(question.strip()):
        return "calculator", {"expr": question.replace("^", "**")}
    return "search_docs", {"query": question}


def run(question: str) -> dict:
    blocked = refusal(question)
    if blocked:
        return {"answer": blocked, "mode": "guardrail"}
    if os.getenv("OPENAI_API_KEY"):
        return _run_llm(question)
    name, args = route(question)
    return {"answer": TOOLS[name](**args), "tool": name, "mode": "router"}


def _run_llm(question: str) -> dict:
    from langgraph.prebuilt import create_react_agent
    from langchain_openai import ChatOpenAI
    from langchain_core.tools import tool

    model = ChatOpenAI(model=os.getenv("MODEL", "gpt-4o-mini"))
    graph = create_react_agent(model, [tool(fn) for fn in TOOLS.values()])
    out = graph.invoke({"messages": [("user", question)]})
    return {"answer": out["messages"][-1].content, "mode": "llm"}

