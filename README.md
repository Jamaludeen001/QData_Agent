# QData Agent

> A fully custom, production-ready data analyst agent architected from the ground up — no LangChain AgentExecutor, no black box. Powered by MCP for tool orchestration, secured with JWT authentication (AWS KMS in production, local secret in dev), supports both CSV (dev) and Amazon Redshift (prod) as data sources, fully observable via LangSmith with per-run audit trails and user feedback scoring, and an LLM-based intent classifier that understands natural conversation. Every layer is owned, auditable, and production-hardened.

---

## Why QData Agent?

Most agents are built on framework abstractions that hide what's really happening.
QData Agent owns every layer:

- **Custom agent loop** — no AgentExecutor, full control over every decision
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
client.py
    │
    │  Streamable HTTP + JWT (HS256 dev / RS256 prod)
    ▼
server.py (MCP Server — http://localhost:8000/mcp)
    │
    ├── tool_inspect_source_schema   ← schema.table listing (dev) / Redshift schema (prod)
    ├── tool_query_source            ← AST validated, SELECT only
    ├── tool_load_source_into_temp
    ├── tool_query_temp              ← sandboxed DuckDB, source never touched
    └── tool_list_temp_tables
    │
    ▼
tools/          ← each tool as an isolated package
core/           ← validators, pathguard, duckdb runner, redshift runner
agent/          ← custom loop with structured output, audit, classifier
auth/           ← JWT handler (KMS prod / local dev)
config.py       ← single source of truth, ENV flag switches dev/prod
```

---

## Project Structure

```
QData_Agent/
│
├── server.py                        # MCP server — exposes all tools over Streamable HTTP
├── client.py                        # MCP client — connects to server, runs agent loop
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
│   ├── audit.py                     # LangSmith audit — every run + tool call logged
│   └── classifier.py                # LLM-based intent classifier with structured output
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
User: "Show top 5 customers by revenue"

Step 1 → tool_inspect_source_schema()
       ← Schema: sales
            Table: customers  SQL name: sales.customers
            Table: orders     SQL name: sales.orders

Step 2 → tool_query_source(
            sql="SELECT c.name, SUM(o.revenue) as total
                 FROM sales.customers c
                 JOIN sales.orders o ON c.id = o.customer_id
                 GROUP BY c.name ORDER BY total DESC LIMIT 5")
       ← results table

Final  → "The top 5 customers by revenue are: ..."
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
```

**5. Start the agent**

```bash
python client.py
```

---

## Environment Variables

### Dev

| Variable | Required | Description |
|---|---|---|
| `ENV` | Yes | Set to `dev` |
| `LANGCHAIN_API_KEY` | Yes | LangSmith API key |
| `GOOGLE_API_KEY` | Yes | Google AI Studio key |
| `JWT_SECRET` | Yes | Min 32 char secret |
| `MCP_SERVER_URL` | Yes | MCP server endpoint |

### Production

| Variable | Required | Description |
|---|---|---|
| `ENV` | Yes | Set to `prod` |
| `LANGCHAIN_API_KEY` | Yes | LangSmith API key |
| `KMS_KEY_ID` | Yes | AWS KMS key ARN |
| `REDSHIFT_HOST` | Yes | Redshift cluster endpoint |
| `REDSHIFT_DATABASE` | Yes | Redshift database name |
| `MCP_SERVER_URL` | Yes | MCP server endpoint |

---

## License

MIT
