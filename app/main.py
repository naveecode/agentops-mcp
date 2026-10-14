import json

from fastapi import FastAPI
from pydantic import BaseModel

from . import agent, cache
from .queue import enqueue, uses_broker
from .store import get_store

app = FastAPI(title="AgentOps MCP")


class Ask(BaseModel):
    question: str


class Doc(BaseModel):
    id: str
    text: str


@app.get("/health")
def health():
    return {
        "ok": True,
        "store": get_store().backend,
        "queue": "rabbitmq" if uses_broker() else "inline",
        "cache": cache.backend(),
    }


@app.post("/docs")
def add(document: Doc):
    return enqueue(document.id, document.text)


@app.get("/chats")
def chats(limit: int = 20):
    return {"chats": get_store().recent_chats(limit)}


@app.post("/ask")
def ask(body: Ask):
    key = "ask:" + body.question
    cached = cache.get(key)
    if cached:
        return {**json.loads(cached), "cached": True}
    result = agent.run(body.question)
    cache.set(key, json.dumps(result, default=str))
    get_store().add_chat({
        "question": body.question,
        "answer": result["answer"],
        "mode": result.get("mode"),
        "tool": result.get("tool"),
    })
    return {**result, "cached": False}
