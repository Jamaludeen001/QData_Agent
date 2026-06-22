import uuid
import logging
from typing import Dict, Any, List, Tuple, Literal
from pydantic import BaseModel, Field
from mcp import ClientSession
from agent.audit import LangSmithAudit

logger = logging.getLogger(__name__)


class AgentDecision(BaseModel):
    type:   Literal["action", "final"]
    tool:   str | None            = Field(default=None)
    input:  Dict[str, Any] | None = Field(default=None)
    answer: str | None            = Field(default=None)


def format_scratchpad(steps: List[Tuple[str, str, str]]) -> str:
    buf = []
    for idx, (act, inp, obs) in enumerate(steps, start=1):
        buf.append(f"Step {idx}")
        buf.append(f"Action: {act}")
        buf.append(f"Input: {inp}")
        buf.append(f"Observation: {obs}")
        buf.append("")
    return "\n".join(buf)


def build_system_prompt(tools: list) -> str:
    tool_docs = "\n".join(
        f"- {t['name']}: {t['description']}"
        for t in tools
    )
    return f"""You are a data analyst assistant that solves tasks step by step.

Available tools:
{tool_docs}

Rules:
- Decide ONE action at a time.
- If you need to use a tool set type to 'action', provide tool name and input dict.
- If you have the final answer set type to 'final', provide the answer string.
- Always call tool_inspect_source_schema first before any query.

SQL Rules:
- Source data is organised as schemas containing tables.
- Table name in SQL = schema.table (dot notation)
- Examples:
    schema1/customers.csv  → SELECT * FROM schema1.customers
    schema2/orders.csv     → SELECT * FROM schema2.orders
- Cross schema join:
    SELECT * FROM schema1.customers c
    JOIN schema2.orders o ON c.id = o.customer_id
- NEVER use filename or path in SQL:
    Wrong: SELECT * FROM customers.csv
    Wrong: SELECT * FROM schema1/customers
    Correct: SELECT * FROM schema1.customers"""


class FullyCustomAgent:
    def __init__(
        self,
        llm,
        session_id:   str,
        max_steps:    int = 8,
        truncate_obs: int = 1500,
    ):
        self.llm            = llm
        self.session_id     = session_id
        self.max_steps      = max_steps
        self.truncate_obs   = truncate_obs
        self.audit          = LangSmithAudit(session_id)
        self.structured_llm = llm.with_structured_output(AgentDecision)

    def _call_llm(self, messages: list) -> AgentDecision:
        return self.structured_llm.invoke(messages)

    def _build_messages(
        self,
        user_query:    str,
        history:       list,
        steps:         List[Tuple[str, str, str]],
        system_prompt: str,
    ) -> list:
        scratchpad_text = format_scratchpad(steps)
        messages = [{"role": "system", "content": system_prompt}]
        for h in history:
            messages.append(h)
        messages.append({"role": "user", "content": user_query})
        if scratchpad_text.strip():
            messages.append({
                "role":    "assistant",
                "content": f"Scratchpad so far:\n{scratchpad_text}"
            })
        return messages

    async def run(
        self,
        user_query:      str,
        history:         List[Dict],
        mcp_session:     ClientSession,
        available_tools: list,
    ) -> Dict[str, Any]:

        steps         = []
        run_id        = str(uuid.uuid4())
        tool_names    = [t["name"] for t in available_tools]
        system_prompt = build_system_prompt(available_tools)

        for step_idx in range(1, self.max_steps + 1):
            messages = self._build_messages(user_query, history, steps, system_prompt)

            try:
                decision = self._call_llm(messages)
            except Exception as e:
                logger.warning("LLM call failed at step %d: %s", step_idx, e)
                steps.append(("llm_error", "", f"LLM error: {e}"))
                continue

            logger.debug(
                "Step %d decision: type=%s tool=%s",
                step_idx, decision.type, decision.tool
            )

            # ── Final answer ──────────────────────────────────────────────────
            if decision.type == "final":
                answer = (decision.answer or "").strip()
                self.audit.log_run(user_query, answer, steps, "final_answer", run_id)
                return {
                    "final_answer": answer,
                    "steps":        steps,
                    "terminated":   "final_answer",
                    "run_id":       run_id,
                }

            # ── Tool action ───────────────────────────────────────────────────
            if decision.type == "action":
                tool_name  = decision.tool  or ""
                tool_input = decision.input or {}

                if tool_name not in tool_names:
                    steps.append((
                        tool_name, str(tool_input),
                        f"Invalid tool '{tool_name}'. Available: {tool_names}"
                    ))
                    continue

                tool_schema = next(
                    (t["input_schema"] for t in available_tools if t["name"] == tool_name), {}
                )
                if "session_id" in tool_schema.get("properties", {}):
                    tool_input["session_id"] = self.session_id

                try:
                    result      = await mcp_session.call_tool(tool_name, tool_input)
                    observation = str(result.content[0].text if result.content else "No result")
                except Exception as e:
                    observation = f"ToolError: {type(e).__name__}: {e}"

                if len(observation) > self.truncate_obs:
                    observation = observation[:self.truncate_obs] + " ... [truncated]"

                steps.append((tool_name, str(tool_input), observation))
                continue

            # ── Unknown type ──────────────────────────────────────────────────
            steps.append((
                "unknown_type", str(decision),
                "Unknown decision type. Use action or final only."
            ))
            continue

        # ── Max steps reached ─────────────────────────────────────────────────
        logger.warning("Max steps reached for query: %s", user_query)
        messages = self._build_messages(user_query, history, steps, system_prompt)
        messages.append({
            "role":    "user",
            "content": "Max steps reached. Give your best final answer now."
        })
        try:
            decision = self._call_llm(messages)
            ans      = (decision.answer or "Max steps reached.").strip()
        except Exception:
            ans = "Max steps reached. Could not produce final answer."

        self.audit.log_run(user_query, ans, steps, "max_steps", run_id)
        return {
            "final_answer": ans,
            "steps":        steps,
            "terminated":   "max_steps",
            "run_id":       run_id,
        }
