from pydantic import BaseModel
from typing import Literal


class RoutingDecision(BaseModel):
    intent:  Literal["CHITCHAT", "DATA_QUERY", "CLARIFICATION"]
    reason:  str    # why this intent was chosen — useful for LangSmith audit


def route_message(message: str, llm) -> RoutingDecision:
    """
    Fast intent router — runs before agent loop.
    Decides whether to use tools or respond directly.
    Uses structured output so result is always valid.
    """
    structured_llm = llm.with_structured_output(RoutingDecision)

    messages = [
        {"role": "system", "content": """You are an intent router for a data analyst assistant.

Classify the user message into exactly one of these intents:

CHITCHAT:
- Greetings and small talk: "hi", "hello", "how are you", "good morning", "who are you"
- General knowledge questions unrelated to data: "what is AI", "explain machine learning"
- Acknowledgements: "ok", "thanks", "got it", "sure", "sounds good"
- Follow up to a previous answer that doesn't need new data: "can you explain that more"

DATA_QUERY:
- Any question that requires querying, analysing, or exploring data
- Questions about tables, schemas, columns, rows
- Aggregations, filters, joins, comparisons involving data
- "show me", "how many", "what is the total", "list all", "find", "get"
- Even vague data questions: "what data do we have", "what schemas are available"

CLARIFICATION:
- Message is too vague to understand what data they want
- Missing critical info needed to proceed: "analyse this" (analyse what?)
- Ambiguous intent that could be chitchat or data

Also provide a short reason for your decision."""},
        {"role": "user", "content": message},
    ]

    try:
        return structured_llm.invoke(messages)
    except Exception:
        # Default to DATA_QUERY on failure — safer than skipping tools
        return RoutingDecision(intent="DATA_QUERY", reason="Router failed, defaulting to data query")
