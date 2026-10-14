"""MCP server exposing the same tools (run: python -m app.mcp_server)."""
from mcp.server.fastmcp import FastMCP
from .tools import calculator, search_docs
mcp=FastMCP("agentops")
mcp.tool()(calculator); mcp.tool()(search_docs)
if __name__=="__main__": mcp.run()
