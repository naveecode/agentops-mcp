"""MCP server advertises the same tools the agent calls, and they execute."""
import asyncio

from app.mcp_server import mcp
from app.tools import add_doc


def test_mcp_registers_agent_tools():
    tools = asyncio.run(mcp.list_tools())
    names = sorted(tool.name for tool in tools)
    assert names == ["calculator", "search_docs"]
    assert all(tool.description for tool in tools)


def test_mcp_calculator_matches_agent_tool():
    result = asyncio.run(mcp.call_tool("calculator", {"expr": "2*(3+4)"}))
    assert result.is_error is False
    assert result.structured_content["result"] == 14


def test_mcp_search_reads_ingested_docs():
    add_doc("d1", "refund policy is 30 days")
    result = asyncio.run(mcp.call_tool("search_docs", {"query": "refund policy"}))
    assert result.is_error is False
    hits = result.structured_content["result"]
    assert hits[0]["id"] == "d1"
