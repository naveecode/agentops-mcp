"""MCP server exposing the same tools (run: python -m app.mcp_server)."""
from mcp.server.mcpserver import MCPServer
from .tools import calculator, search_docs

mcp = MCPServer("agentops")
mcp.tool()(calculator)
mcp.tool()(search_docs)

if __name__ == "__main__":
    mcp.run()
