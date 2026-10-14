import json, os
from fastapi import FastAPI
from pydantic import BaseModel
from . import agent, tools
app=FastAPI(title="AgentOps MCP")
_cache={}
try:
    import redis; _r=redis.from_url(os.environ["REDIS_URL"]) if os.getenv("REDIS_URL") else None
except ImportError: _r=None
class Ask(BaseModel): question:str
class Doc(BaseModel): id:str; text:str
@app.get("/health")
def health(): return {"ok":True}
@app.post("/docs")
def add(d:Doc): return {"id":tools.add_doc(d.id,d.text)}
@app.post("/ask")
def ask(a:Ask):
    k="ask:"+a.question
    hit=_r.get(k) if _r else _cache.get(k)
    if hit: return {**json.loads(hit),"cached":True}
    res=agent.run(a.question); s=json.dumps(res,default=str)
    _r.setex(k,3600,s) if _r else _cache.__setitem__(k,s)
    return {**res,"cached":False}
