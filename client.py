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
        generation_config = {
            "thinking_config": {"thinking_budget": 1024}
        }
    )
    classifier_llm = ChatGoogleGenerativeAI(
        model             = "gemini-3.5-flash",
        temperature       = 0,
        max_output_tokens = 500,
        generation_config = {
            "thinking_config": {"thinking_budget": 0}
        }
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

                    intent = classify_intent(user_input, classifier_llm)

                    if intent == "POSITIVE_FEEDBACK" and last_run_id:
                        audit.log_feedback(last_run_id, score=1.0, comment=user_input)
                        print("Bot: Glad that helped!\n")
                        continue

                    if intent == "NEGATIVE_FEEDBACK" and last_run_id:
                        audit.log_feedback(last_run_id, score=0.0, comment=user_input)
                        print("Bot: Sorry! What were you looking for exactly?\n")
                        continue

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
