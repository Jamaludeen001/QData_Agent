# QData Agent

> A fully custom, production-ready data analyst agent architected from the ground up — no LangChain AgentExecutor, no black box. Powered by MCP for tool orchestration, secured with JWT authentication (AWS KMS in production, local secret in dev), supports both CSV (dev) and Amazon Redshift (prod) as data sources, fully observable via LangSmith with per-run audit trails and user feedback scoring, an LLM-based intent classifier, and a production-grade router that separates normal conversation from data queries — no tools fired unless actually needed. Every layer is owned, auditable, and production-hardened.

---

## Why QData Agent?

Most agents are built on framework abstractions that hide what's really happening.
QData Agent owns every layer:

- **Custom agent loop** — no AgentExecutor, full control over every decision
- **Production-grade router** — separates chitchat from data queries before agent runs
- **Structured output** — LLM forced to return valid schema via Pydantic, zero parse errors
- **AST-level SQL validation** — not keyword filtering, actual parse tree analysis
- **MCP architecture** — tools live as an independent Streamable HTTP service
- **Schema/table organisation** — source data organised as schemas containing tables
- **Dev / Prod parity** — CSV + DuckDB for dev, Amazon Redshift for prod
- **JWT authentication** — local HS256 secret for dev, AWS KMS RS256 for prod
- **Source / temp separation** — source data is immutable, agent works in sandbox
- **Full audit trail** — every run, every tool call traced in LangSmith

---

## Architecture

```
User input
    │
    ▼
Intent Classifier (feedback detection)
    │
    ├── POSITIVE_FEEDBACK → log score 1.0 to LangSmith
    ├── NEGATIVE_FEEDBACK → log score 0.0 to LangSmith
    └── CONTINUATION
            │
            ▼
        Router (intent routing)
            │
            ├── CHITCHAT      → direct_respond (no tools, no agent loop)
            ├── CLARIFICATION → ask user for more info
            └── DATA_QUERY
                    │
                    ▼
                Agent Loop (MCP tools)
                    │
                    │  Streamable HTTP + JWT
                    ▼
                MCP Server
                    │
                    ├── tool_inspect_source_schema
                    ├── tool_query_source
                    ├── tool_load_source_into_temp
                    ├── tool_query_temp
                    └── tool_list_temp_tables
```

---

## Project Structure

```
QData_Agent/
│
├── server.py                        # MCP server — exposes all tools over Streamable HTTP
├── client.py                        # MCP client — router + agent loop
│
├── tools/
│   ├── schema_inspector/
│   │   └── tool.py                  # schema/table listing (dev) / Redshift schema (prod)
│   ├── source_query/
│   │   └── tool.py                  # READ-ONLY SELECT — DuckDB (dev) / Redshift (prod)
│   ├── temp_loader/
│   │   └── tool.py                  # load source data into temp DuckDB sandbox
│   ├── temp_query/
│   │   └── tool.py                  # run ANY SQL in temp sandbox (always DuckDB)
│   └── temp_inspector/
│       └── tool.py                  # list all tables in temp sandbox
│
├── core/
│   ├── validators.py                # AST-level SQL validation via sqlglot
│   ├── pathguard.py                 # path traversal guard (dev)
│   ├── duckdb_runner.py             # DuckDB execution — schema views + temp sandbox
│   └── redshift_runner.py           # Redshift execution — prod SSO connection
│
├── agent/
│   ├── agent.py                     # fully custom agent loop with structured output
│   ├── router.py                    # intent router — chitchat vs data query vs clarification
│   ├── responder.py                 # direct conversation handler for chitchat
│   ├── classifier.py                # feedback classifier — positive / negative / continuation
│   └── audit.py                     # LangSmith audit — every run + tool call logged
│
├── auth/
│   ├── __init__.py
│   └── jwt_handler.py               # HS256 local (dev) / RS256 KMS (prod)
│
├── data/
│   └── source/                      # place schema subfolders here
│       ├── schema1/
│       │   ├── customers.csv
│       │   └── orders.csv
│       └── schema2/
│           └── transactions.csv
│
├── config.py                        # all env vars, ENV flag, folder paths
├── .env.example                     # environment variable template
└── requirements.txt
```

---

## Dev vs Production

| | Dev | Production |
|---|---|---|
| Data source | CSV files via DuckDB | Amazon Redshift (SSO) |
| SQL notation | schema.table (dot notation) | schema.table (Redshift native) |
| JWT signing | HS256 local secret | RS256 AWS KMS |
| Permissions | Path traversal guard | Redshift native (SSO enforces) |
| Temp sandbox | DuckDB | DuckDB |
| AST validation | ✅ | ✅ |
| LangSmith audit | ✅ | ✅ |
| Switch | `ENV=dev` | `ENV=prod` |

---

## Security Layers

| Layer | How |
|---|---|
| AST-level SQL validation | sqlglot parses SQL into syntax tree — mutations blocked at parse time |
| Source / temp separation | Source data is read-only views — agent sandbox is isolated DuckDB session |
| Path traversal guard | Resolved path checked against allowed folder before every file access (dev) |
| JWT authentication | Every MCP request requires signed JWT — HS256 (dev) or KMS RS256 (prod) |
| Redshift SSO | Prod queries run as the actual user — Redshift enforces permissions natively |
| Session isolation | Each conversation gets its own DuckDB `.db` file in temp folder |
| Session cleanup | Temp database wiped automatically when conversation ends |
| Structured output | LLM forced to return Pydantic-validated schema — no prompt injection via malformed JSON |

---

## How the Agent Thinks

```
User: "hi"
    → classifier  : CONTINUATION
    → router      : CHITCHAT
    → responder   : "Hello! How can I help you today?"
    → no tools fired ✅

User: "show top 5 customers by revenue"
    → classifier  : CONTINUATION
    → router      : DATA_QUERY
    → agent loop  :
        Step 1 → tool_inspect_source_schema()
               ← Schema: sales → customers, orders
        Step 2 → tool_query_source(
                    sql="SELECT c.name, SUM(o.revenue) as total
                         FROM sales.customers c
                         JOIN sales.orders o ON c.id = o.customer_id
                         GROUP BY c.name ORDER BY total DESC LIMIT 5")
               ← results
        Final  → "The top 5 customers by revenue are..."  ✅

User: "great thanks"
    → classifier  : POSITIVE_FEEDBACK
    → LangSmith   : score 1.0 logged ✅
```

---

## Observability

Every conversation turn is fully traced in LangSmith:

```
Run (chain)
 ├── tool_inspect_source_schema     (tool)
 ├── tool_query_source              (tool)
 └── Final answer                   (output)
```

- Every tool call logged as a child run under the parent trace
- User feedback tied to `run_id` — thumbs up scores `1.0`, thumbs down `0.0`
- Session ID threads through every trace for full conversation audit
- Termination reason recorded — `final_answer`, `max_steps`, or error
- Router decisions logged at DEBUG level

---

## Quickstart

**1. Clone and install**

```bash
git clone https://github.com/yourusername/QData_Agent.git
cd QData_Agent
pip install -r requirements.txt
```

**2. Configure environment**

```bash
cp .env.example .env
```

Generate JWT secret:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Edit `.env`:
```
ENV=dev
LANGCHAIN_API_KEY=ls__...
GOOGLE_API_KEY=your-google-ai-studio-key
JWT_SECRET=your-generated-secret
MCP_SERVER_URL=http://localhost:8000/mcp
```

**3. Add your CSV files**

```
data/source/
├── sales/
│   ├── customers.csv
│   └── orders.csv
└── finance/
    └── transactions.csv
```

**4. Start MCP server**

```bash
python server.py

# QData Agent MCP Server starting...
# Endpoint     : http://0.0.0.0:8000/mcp
# Health check : http://0.0.0.0:8000/health
# Transport    : Streamable HTTP
# Auth         : JWT (Local HS256)
# Data source  : CSV (DuckDB)
```

**5. Start the agent**

```bash
python client.py

# Session    : abc-123...
# MCP Server : http://localhost:8000/mcp
# Mode       : Dev (CSV)
#
# Tools available (5):
#   - tool_inspect_source_schema
#   - tool_query_source
#   - tool_load_source_into_temp
#   - tool_query_temp
#   - tool_list_temp_tables
#
# You:
```

---

## Example Conversations

```
You: hi
Bot: Hello! How can I help you today?

You: what schemas do we have?
Bot: [inspects schema] You have sales (customers, orders) and finance (transactions).

You: show me top 5 customers by revenue
Bot: [queries data] The top 5 customers by revenue are...

You: great thanks
Bot: Glad that helped!

You: what is machine learning?
Bot: Machine learning is a field of AI where systems learn from data...

You: analyse this
Bot: Could you be more specific? Which table or schema are you interested in?

You: that last answer was wrong
Bot: Sorry! What were you looking for exactly?

You: exit
Session cleaned up.
```

---

## Environment Variables

### Dev

| Variable | Required | Description |
|---|---|---|
| `ENV` | Yes | Set to `dev` |
| `LANGCHAIN_API_KEY` | Yes | LangSmith API key |
| `GOOGLE_API_KEY` | Yes | Google AI Studio key |
| `JWT_SECRET` | Yes | Min 32 char secret — generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `MCP_SERVER_URL` | Yes | MCP server endpoint URL |
| `LANGCHAIN_PROJECT` | No | LangSmith project name (default: `QData_Agent`) |

### Production

| Variable | Required | Description |
|---|---|---|
| `ENV` | Yes | Set to `prod` |
| `LANGCHAIN_API_KEY` | Yes | LangSmith API key |
| `KMS_KEY_ID` | Yes | AWS KMS key ARN for JWT RS256 signing |
| `REDSHIFT_HOST` | Yes | Redshift cluster endpoint |
| `REDSHIFT_DATABASE` | Yes | Redshift database name |
| `REDSHIFT_PORT` | No | Redshift port (default: `5439`) |
| `MCP_SERVER_URL` | Yes | MCP server endpoint URL |
| `ISSUER` | No | JWT issuer (default: `qdataagent-client`) |
| `AUDIENCE` | No | JWT audience (default: `qdataagent-mcp-server`) |
| `ACCESS_TTL` | No | JWT expiry in seconds (default: `3600`) |

---

## Requirements

```
python >= 3.11
langchain-openai
langchain-google-genai
langsmith
mcp
fastmcp
uvicorn
duckdb
sqlglot
pandas
python-dotenv
starlette
pyjwt
boto3
redshift-connector
fastapi
python-multipart
argon2-cffi
httpx
pydantic
google-generativeai
```

---

## What's Not Included (intentionally)

This project is intentionally kept minimal and auditable. The following are out of scope until the foundation is fully tested:

- RAG / vector search
- Web UI
- Multi-agent orchestration
- Docker deployment

---

## License

MIT
