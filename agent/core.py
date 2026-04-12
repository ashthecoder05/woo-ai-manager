from __future__ import annotations
import json
import logging
from openai import AzureOpenAI

logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 8
from config import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_DEPLOYMENT,
    AZURE_OPENAI_API_VERSION,
)
from agent.system_prompt import build_system_prompt
from agent.tools import TOOL_DEFINITIONS, run_tool

client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_version=AZURE_OPENAI_API_VERSION,
)


def chat(messages: list[dict], gateway: str = "blockonomics", merchant_email: str = "") -> str:
    """Run the agentic loop and return the final text response.

    Args:
        messages: Conversation messages.
        gateway: The merchant's payment gateway (blockonomics, stripe, etc.).
                 Controls which system prompt variant the agent uses.
        merchant_email: The logged-in merchant's email. Passed to data tools so
                        they return only that merchant's orders/payments.
    """
    system_prompt = build_system_prompt(gateway)
    history = [{"role": "system", "content": system_prompt}] + list(messages)

    for iteration in range(MAX_TOOL_ITERATIONS):
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

            for tc in tool_calls:
                inputs = json.loads(tc.function.arguments)
                output = run_tool(tc.function.name, inputs, merchant_email=merchant_email)
                history.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": output,
                })
            continue

        # Fallback for unexpected finish reasons
        return choice.message.content or "I could not generate a response."

    # If we exhausted all iterations, force a final text-only response
    logger.warning("Agent hit max tool iterations (%d), forcing final response", MAX_TOOL_ITERATIONS)
    history.append({
        "role": "user",
        "content": "Please provide your final answer now based on the information you have gathered.",
    })
    response = client.chat.completions.create(
        model=AZURE_OPENAI_DEPLOYMENT,
        max_tokens=1024,
        messages=history,
    )
    return response.choices[0].message.content or "I could not generate a response."
