import asyncio
import uuid
import logging
from typing import List
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession
from langchain_google_genai import ChatGoogleGenerativeAI
from langsmith import Client
from agent.agent import FullyCustomAgent
from agent.audit import LangSmithAudit
from agent.classifier import classify_intent
from agent.router import route_message
from agent.responder import direct_respond
from core.duckdb_runner import cleanup_session
from auth.jwt_handler import generate_service_token
from config import SOURCE_FOLDER, MCP_SERVER_URL, IS_PROD

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)
smith  = Client()


async def main():
    session_id  = str(uuid.uuid4())
    history     = []
    last_run_id = None

    llm = ChatGoogleGenerativeAI(
        model             = "gemini-3.5-flash",
        temperature       = 0,
        max_output_tokens = 2000,
        generation_config = {"thinking_config": {"thinking_budget": 1024}}
    )
    classifier_llm = ChatGoogleGenerativeAI(
        model             = "gemini-3.5-flash",
        temperature       = 0,
        max_output_tokens = 500,
        generation_config = {"thinking_config": {"thinking_budget": 0}}
    )
    # Router uses cheapest/fastest — just classifying intent
    router_llm = ChatGoogleGenerativeAI(
        model             = "gemini-3.5-flash",
        temperature       = 0,
        max_output_tokens = 100,
        generation_config = {"thinking_config": {"thinking_budget": 0}}
    )

    redshift_username = None
    redshift_password = None
    if IS_PROD:
        redshift_username = input("Redshift username: ").strip()
        redshift_password = input("Redshift password: ").strip()

    service_token = generate_service_token(
        user_id  = session_id,
        metadata = {
            "redshift_username": redshift_username,
            "redshift_password": redshift_password,
        } if IS_PROD else {}
    )
    auth_headers = {"Authorization": f"Bearer {service_token}"}

    agent = FullyCustomAgent(llm=llm, session_id=session_id)
    audit = LangSmithAudit(session_id=session_id)

    print(f"\nSession    : {session_id}")
    print(f"MCP Server : {MCP_SERVER_URL}")
    print(f"Mode       : {'Production (Redshift)' if IS_PROD else 'Dev (CSV)'}")
    if not IS_PROD:
        print(f"Source     : {SOURCE_FOLDER.resolve()}")
    print("Connecting to MCP server...\n")

    async with streamablehttp_client(
        url     = MCP_SERVER_URL,
        headers = auth_headers,
    ) as (read, write, _):
        async with ClientSession(read, write) as mcp_session:

            await mcp_session.initialize()
            tools_response  = await mcp_session.list_tools()
            available_tools = [
                {
                    "name":         t.name,
                    "description":  t.description,
                    "input_schema": t.inputSchema,
                }
                for t in tools_response.tools
            ]

            print(f"Tools available ({len(available_tools)}):")
            for t in available_tools:
                print(f"  - {t['name']}")
            print()

            try:
                while True:
                    user_input = input("You: ").strip()
                    if not user_input:
                        continue
                    if user_input.lower() == "exit":
                        break

                    # ── Step 1: Feedback classification ───────────────────────
                    intent = classify_intent(user_input, classifier_llm)

                    if intent == "POSITIVE_FEEDBACK" and last_run_id:
                        audit.log_feedback(last_run_id, score=1.0, comment=user_input)
                        print("Bot: Glad that helped!\n")
                        history.append({"role": "user",      "content": user_input})
                        history.append({"role": "assistant",  "content": "Glad that helped!"})
                        continue

                    if intent == "NEGATIVE_FEEDBACK" and last_run_id:
                        audit.log_feedback(last_run_id, score=0.0, comment=user_input)
                        print("Bot: Sorry! What were you looking for exactly?\n")
                        history.append({"role": "user",      "content": user_input})
                        history.append({"role": "assistant",  "content": "Sorry! What were you looking for exactly?"})
                        continue

                    # ── Step 2: Route — chitchat or data query ────────────────
                    routing = route_message(user_input, router_llm)
                    logger.debug("Router: intent=%s reason=%s", routing.intent, routing.reason)

                    if routing.intent == "CHITCHAT":
                        # ── Direct response — no tools, no agent loop ─────────
                        response = direct_respond(user_input, history, llm)
                        print(f"Bot: {response}\n")
                        history.append({"role": "user",      "content": user_input})
                        history.append({"role": "assistant",  "content": response})
                        continue

                    if routing.intent == "CLARIFICATION":
                        # ── Ask user to clarify ───────────────────────────────
                        response = "Could you be more specific? For example, which table or schema are you interested in?"
                        print(f"Bot: {response}\n")
                        history.append({"role": "user",      "content": user_input})
                        history.append({"role": "assistant",  "content": response})
                        continue

                    # ── Step 3: DATA_QUERY — run full agent with tools ─────────
                    result      = await agent.run(
                        user_input, history, mcp_session, available_tools
                    )
                    last_run_id = result["run_id"]

                    history.append({"role": "user",      "content": user_input})
                    history.append({"role": "assistant",  "content": result["final_answer"]})

                    print(f"Bot: {result['final_answer']}\n")

            finally:
                cleanup_session(session_id)
                print("Session cleaned up.")


if __name__ == "__main__":
    asyncio.run(main())
