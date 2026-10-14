"""Tools exposed both to the LangGraph agent and the MCP server."""
import ast
import operator as op

from .ingest import ingest_document
from .store import get_store

OPS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.Pow: op.pow,
    ast.USub: op.neg,
}


def calculator(expr: str) -> float:
    """Evaluate a safe arithmetic expression. Supports + - * / ** parentheses and unary minus."""
    def evaluate(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp):
            return OPS[type(node.op)](evaluate(node.left), evaluate(node.right))
        if isinstance(node, ast.UnaryOp):
            return OPS[type(node.op)](evaluate(node.operand))
        raise ValueError("unsupported expression")

    return evaluate(ast.parse(expr, mode="eval").body)


def add_doc(doc_id: str, text: str) -> str:
    ingest_document(doc_id, text)
    return doc_id


def search_docs(query: str, k: int = 3) -> list[dict]:
    """Search ingested documents. Returns the top matches with id, text, and score."""
    return get_store().search(query, k=k)


TOOLS = {"calculator": calculator, "search_docs": search_docs}
