from __future__ import annotations
import json
from openai import AzureOpenAI
from config import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_DEPLOYMENT,
    AZURE_OPENAI_API_VERSION,
)
from agent.system_prompt import SYSTEM_PROMPT
from agent.tools import TOOL_DEFINITIONS, run_tool

client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_version=AZURE_OPENAI_API_VERSION,
)


def chat(messages: list[dict]) -> str:
    """Run the agentic loop and return the final text response."""
    history = [{"role": "system", "content": SYSTEM_PROMPT}] + list(messages)

    while True:
        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            max_tokens=1024,
            tools=TOOL_DEFINITIONS,
            messages=history,
        )

        choice = response.choices[0]

        if choice.finish_reason == "stop":
            return choice.message.content or "I could not generate a response."

        if choice.finish_reason == "tool_calls":
            # Add assistant message with tool_calls to history
            tool_calls = choice.message.tool_calls or []
            history.append({
                "role": "assistant",
                "content": choice.message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ],
            })

            # Execute each tool and append results
            for tc in tool_calls:
                inputs = json.loads(tc.function.arguments)
                output = run_tool(tc.function.name, inputs)
                history.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": output,
                })
            continue

        # Fallback
        return choice.message.content or "I could not generate a response."
