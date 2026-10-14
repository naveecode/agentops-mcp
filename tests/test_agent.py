"""The LangGraph path has to actually call tools, not only import."""
import warnings

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

from app.agent import route, run


def test_router_picks_calculator_for_arithmetic():
    assert route("2*(3+4)") == ("calculator", {"expr": "2*(3+4)"})
    assert route("2 ^ 3")[0] == "calculator"
    assert route("2 ^ 3")[1]["expr"] == "2 ** 3"


def test_router_sends_prose_to_search():
    assert route("refund policy") == ("search_docs", {"query": "refund policy"})


def test_langgraph_react_loop_calls_calculator(monkeypatch):
    bound = []

    class Scripted(FakeMessagesListChatModel):
        def bind_tools(self, tools, **kwargs):
            bound.extend(getattr(tool, "name", str(tool)) for tool in tools)
            return self

    fake = Scripted(responses=[
        AIMessage(
            content="",
            tool_calls=[{
                "name": "calculator",
                "args": {"expr": "2*(3+4)"},
                "id": "call-1",
                "type": "tool_call",
            }],
        ),
        AIMessage(content="14"),
    ])
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("MODEL", "gpt-test")

    import langchain_openai

    def chat_openai(*args, **kwargs):
        assert kwargs["model"] == "gpt-test"
        return fake

    monkeypatch.setattr(langchain_openai, "ChatOpenAI", chat_openai)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        result = run("2*(3+4)")
    assert result == {"answer": "14", "mode": "llm"}
    assert bound == ["calculator", "search_docs"]
