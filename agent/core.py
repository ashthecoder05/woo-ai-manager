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


def plugin_chat_with_wc_tools(
    message: str,
    store_url: str,
    consumer_key: str,
    consumer_secret: str,
) -> str:
    """
    Agentic chat loop for the WP plugin using live WooCommerce tool calls.

    The AI decides which WC REST API calls to make, fetches exactly the data
    it needs, and returns a plain-English answer. No static snapshot required.
    """
    from agent.wc_tools import WC_TOOL_DEFINITIONS, run_wc_tool

    system_prompt = f"""You are an AI store manager embedded inside a WooCommerce WP Admin dashboard.
You are talking directly to the STORE OWNER — not a developer, not a customer.

You have live access to the merchant's WooCommerce store via tools. Use them to answer questions
with real, up-to-date data. Always call tools before answering data questions — never guess numbers.

## Rules
- Call multiple tools in parallel when you need data from different sources.
- For write actions (create coupon, update product, update order): present the planned change
  clearly to the merchant and ask for confirmation BEFORE calling the tool. Only proceed once
  they confirm.
- Answer in plain English. No jargon. Be specific — include actual numbers, product names, order IDs.
- If something goes wrong with a tool call, say what failed and suggest what the merchant can do.
- The merchant's store is at: {store_url}
"""

    history = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": message},
    ]

    for _ in range(MAX_TOOL_ITERATIONS):
        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            max_tokens=1024,
            temperature=0.3,
            tools=WC_TOOL_DEFINITIONS,
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
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in tool_calls
                ],
            })

            for tc in tool_calls:
                inputs = json.loads(tc.function.arguments)
                output = run_wc_tool(
                    tc.function.name, inputs,
                    store_url=store_url,
                    consumer_key=consumer_key,
                    consumer_secret=consumer_secret,
                )
                history.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": output,
                })
            continue

        return choice.message.content or "I could not generate a response."

    # Exhausted iterations — force a final answer
    logger.warning("plugin_chat_with_wc_tools hit max iterations, forcing final response")
    history.append({
        "role": "user",
        "content": "Please give your final answer based on the data you've gathered.",
    })
    response = client.chat.completions.create(
        model=AZURE_OPENAI_DEPLOYMENT,
        max_tokens=1024,
        messages=history,
    )
    return response.choices[0].message.content or "I could not generate a response."
