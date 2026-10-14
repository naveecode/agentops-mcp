"""Tools exposed both to the LangGraph agent and the MCP server."""
import ast, operator as op
OPS={ast.Add:op.add,ast.Sub:op.sub,ast.Mult:op.mul,ast.Div:op.truediv,ast.Pow:op.pow,ast.USub:op.neg}
def calculator(expr:str)->float:
    """Evaluate a safe arithmetic expression. Supports + - * / ** parentheses and unary minus."""
    def ev(n):
        if isinstance(n,ast.Constant) and isinstance(n.value,(int,float)): return n.value
        if isinstance(n,ast.BinOp): return OPS[type(n.op)](ev(n.left),ev(n.right))
        if isinstance(n,ast.UnaryOp): return OPS[type(n.op)](ev(n.operand))
        raise ValueError("unsupported expression")
    return ev(ast.parse(expr,mode="eval").body)
DOCS={}
def add_doc(doc_id:str,text:str)->str: DOCS[doc_id]=text; return doc_id
def search_docs(query:str,k:int=3)->list[dict]:
    """Search ingested documents. Returns the top matches with id, text, and score."""
    q=set(query.lower().split())
    scored=sorted(((len(q&set(t.lower().split())),i) for i,t in DOCS.items()),reverse=True)
    return [{"id":i,"text":DOCS[i][:300],"score":s} for s,i in scored[:k] if s>0]
TOOLS={"calculator":calculator,"search_docs":search_docs}
