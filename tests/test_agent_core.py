from types import SimpleNamespace
from unittest.mock import Mock, call, patch

import pytest

from agent import core


def _response(finish_reason, content=None, tool_calls=None):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason=finish_reason,
                message=SimpleNamespace(content=content, tool_calls=tool_calls),
            )
        ]
    )


def _tool_call(call_id, name, arguments):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )


def test_chat_returns_plain_text_response():
    with patch.object(
        core.client.chat.completions,
        "create",
        return_value=_response("stop", "Hello"),
    ):
        assert core.chat([{"role": "user", "content": "Hi"}]) == "Hello"


def test_chat_dispatches_single_tool_call_and_returns_follow_up():
    tool_call = _tool_call("call-1", "get_orders", '{"limit": 2}')
    create = Mock(
        side_effect=[
            _response("tool_calls", tool_calls=[tool_call]),
            _response("stop", "Done"),
        ]
    )

    with (
        patch.object(core.client.chat.completions, "create", create),
        patch.object(core, "run_tool", return_value='{"orders": []}') as run_tool,
    ):
        assert core.chat([], merchant_email="owner@example.com") == "Done"

    run_tool.assert_called_once_with(
        "get_orders",
        {"limit": 2},
        merchant_email="owner@example.com",
    )
    assert create.call_args_list[1].kwargs["messages"][-1] == {
        "role": "tool",
        "tool_call_id": "call-1",
        "content": '{"orders": []}',
    }


def test_chat_dispatches_multiple_tool_calls_in_order():
    tool_calls = [
        _tool_call("call-1", "get_orders", "{}"),
        _tool_call("call-2", "get_products", '{"limit": 5}'),
    ]

    with (
        patch.object(
            core.client.chat.completions,
            "create",
            side_effect=[
                _response("tool_calls", tool_calls=tool_calls),
                _response("stop", "Done"),
            ],
        ),
        patch.object(core, "run_tool", side_effect=["orders", "products"]) as run_tool,
    ):
        assert core.chat([]) == "Done"

    assert run_tool.call_args_list == [
        call("get_orders", {}, merchant_email=""),
        call("get_products", {"limit": 5}, merchant_email=""),
    ]


def test_chat_forces_text_response_after_iteration_limit():
    tool_call = _tool_call("call-1", "get_orders", "{}")
    create = Mock(
        side_effect=[
            *[
                _response("tool_calls", tool_calls=[tool_call])
                for _ in range(core.MAX_TOOL_ITERATIONS)
            ],
            _response("stop", "Final answer"),
        ]
    )

    with (
        patch.object(core.client.chat.completions, "create", create),
        patch.object(core, "run_tool", return_value="orders"),
    ):
        assert core.chat([]) == "Final answer"

    assert create.call_count == core.MAX_TOOL_ITERATIONS + 1
    assert "tools" not in create.call_args.kwargs
    assert create.call_args.kwargs["messages"][-1]["content"].startswith(
        "Please provide your final answer"
    )


def test_chat_propagates_tool_errors():
    tool_call = _tool_call("call-1", "get_orders", "{}")

    with (
        patch.object(
            core.client.chat.completions,
            "create",
            return_value=_response("tool_calls", tool_calls=[tool_call]),
        ),
        patch.object(core, "run_tool", side_effect=RuntimeError("tool failed")),
    ):
        with pytest.raises(RuntimeError, match="tool failed"):
            core.chat([])
