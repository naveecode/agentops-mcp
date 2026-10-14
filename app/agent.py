"""Tool-calling agent. Uses LangGraph + OpenAI-compatible LLM when OPENAI_API_KEY set; else a deterministic router (for tests/demo)."""
import os, re
from .tools import TOOLS
def route(q:str):
    if re.fullmatch(r"[\d\s+\-*/().^]+",q.strip()): return "calculator",{"expr":q.replace("^","**")}
    return "search_docs",{"query":q}
def run(q:str)->dict:
    if os.getenv("OPENAI_API_KEY"):
        from langgraph.prebuilt import create_react_agent
        from langchain_openai import ChatOpenAI
        from langchain_core.tools import tool
        agent=create_react_agent(ChatOpenAI(model=os.getenv("MODEL","gpt-4o-mini")),[tool(f) for f in TOOLS.values()])
        out=agent.invoke({"messages":[("user",q)]})
        return {"answer":out["messages"][-1].content,"mode":"llm"}
    name,args=route(q)
    return {"answer":TOOLS[name](**args),"tool":name,"mode":"router"}
