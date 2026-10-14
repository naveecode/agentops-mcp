# AgentOps MCP

[![ci](https://github.com/naveecode/agentops-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/naveecode/agentops-mcp/actions)

A deployable AI agent service. A LangGraph ReAct agent answers questions over your documents and calls tools. The same tools are exposed as an **MCP server**, so Cursor and Claude Desktop can use them. Documents are chunked, embedded, and stored in MongoDB. Ingest runs inline, or through a RabbitMQ worker that retries and then dead-letters.

## Problem
Teams want one agent that can answer from internal docs, run tools, and be reached two ways: over a REST API, and from AI IDEs over MCP. It should also be cached, testable, and deployable.

## Architecture
```mermaid
flowchart LR
  UI[Next.js UI] --> API[FastAPI /ask]
  API --> C[(Redis cache)]
  API --> AG[LangGraph ReAct agent]
  AG --> T[Tools: search_docs, calculator]
  MCP[MCP server] --> T
  ING[/docs ingest/] --> Q[[RabbitMQ]] --> W[Worker: chunk+embed, retries, DLQ] --> DB[(MongoDB)]
  T --> DB
```
Built: API, LangGraph agent, MCP server, Redis cache, MongoDB document and chat store, RabbitMQ worker, eval harness, Docker, Render and Fly config, CI. Not built yet: the Next.js UI and Kubernetes manifests.

## Quickstart
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload          # http://localhost:8000/docs
docker compose up --build              # API, worker, Redis, MongoDB, RabbitMQ
pytest -q                              # offline tests
python -m app.evals                    # tool accuracy, golden Q&A, guardrails
python -m app.mcp_server               # MCP (stdio) for Cursor/Claude
```
Set `OPENAI_API_KEY` (and optionally `MODEL`, default `gpt-4o-mini`) to use the LangGraph ReAct agent. Without a key, a deterministic router picks the tool, so tests and demos run offline.

```bash
curl -XPOST localhost:8000/docs -H 'content-type: application/json' -d '{"id":"d1","text":"refund policy is 30 days"}'
curl -XPOST localhost:8000/ask  -H 'content-type: application/json' -d '{"question":"refund policy"}'
curl localhost:8000/chats
```

Point Cursor or Claude Desktop at the MCP server:

```json
{ "mcpServers": { "agentops": { "command": "python", "args": ["-m", "app.mcp_server"] } } }
```

## Environment
| Variable | Role |
| --- | --- |
| `OPENAI_API_KEY` | Turns on the LangGraph agent. Unset uses the offline router. |
| `MODEL` | Chat model name. Default `gpt-4o-mini`. |
| `REDIS_URL` | Shared ask-cache. Unset uses process memory. |
| `MONGO_URL` | Document chunks and chat turns. Unset uses memory. |
| `MONGO_DB` | Database name. Default `agentops`. |
| `MONGO_VECTOR_INDEX` | Atlas `$vectorSearch` index on `chunks.embedding`. |
| `RABBITMQ_URL` | Publishes ingest to the worker. Unset ingests inline. |

## Ingest and search
`POST /docs` chunks the text and stores a hashed embedding with each chunk. Without `RABBITMQ_URL` that happens in the request. With it, the API publishes to the `ingest` queue and `python -m app.worker` does the write. A message is attempted three times. The next failure is published to `ingest.dlq`. The broker dead-letters rejected deliveries to that same queue, so a crash does not drop the message.

Search keeps chunks that share a query token and breaks ties with cosine similarity. When `MONGO_VECTOR_INDEX` is set, search tries Atlas `$vectorSearch` first and falls back to the local ranker if the index is unavailable. A new document clears cached `ask:` answers. Across the API and the worker, that invalidation needs Redis.

Guardrails run before any tool. Empty input, questions over 2,000 characters, and prompt-injection phrasing are refused.

## Deploy
`docker compose up --build` starts the API, the worker, Redis, MongoDB, and RabbitMQ.

[render.yaml](render.yaml) is a Render blueprint: a web service on the image, plus a worker running `python -m app.worker`. Supply `OPENAI_API_KEY`, `REDIS_URL` (Upstash), `MONGO_URL` (Atlas), and `RABBITMQ_URL` (CloudAMQP). Set `MONGO_VECTOR_INDEX` when the Atlas index exists.

[fly.toml](fly.toml) runs the same image as an `app` process and a `worker` process. Rename `app` if it is taken, then:

```bash
fly secrets set OPENAI_API_KEY=... REDIS_URL=... MONGO_URL=... RABBITMQ_URL=...
fly deploy
```

CI builds the image and checks `/health`, a document ingest, and `/ask`.

## Roadmap
- [x] MVP: FastAPI, LangGraph agent, MCP server, Redis cache, Docker, CI
- [x] MongoDB document and chat store, with vector search
- [x] RabbitMQ ingest worker with retries and a dead-letter queue
- [x] Eval harness (tool-call accuracy, golden Q&A) and guardrails
- [ ] Next.js (TypeScript) chat UI
- [x] Deploy config: Render and Fly
- [ ] Kubernetes manifests (kind)
