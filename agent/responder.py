def direct_respond(message: str, history: list, llm) -> str:
    """
    Handles CHITCHAT directly — no tools, no agent loop.
    Maintains conversation context via history.
    """
    messages = [
        {"role": "system", "content": """You are a helpful data analyst assistant.
You are having a normal conversation with the user.
Be friendly, concise, and natural.
You have access to data analysis tools but right now the user is just chatting.
If they ask about your capabilities, mention you can analyse data, query tables, and answer data questions."""},
    ]
    for h in history:
        messages.append(h)
    messages.append({"role": "user", "content": message})

    out = llm.invoke(messages)
    if hasattr(out, "content"):
        content = out.content
        if isinstance(content, list):
            content = " ".join(
                c.get("text", "") if isinstance(c, dict) else str(c)
                for c in content
            )
        return content.strip()
    return str(out).strip()
