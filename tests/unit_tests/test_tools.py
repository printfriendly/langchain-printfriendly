"""Standard LangChain unit tests plus behaviour tests for the tool."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx
from langchain_core.tools import BaseTool, ToolException
from langchain_tests.unit_tests import ToolsUnitTests

from langchain_printfriendly import PrintFriendlyError, PrintFriendlyReadPage
from tests.conftest import PAGE, TEST_KEY, generation_error, success_body


class TestPrintFriendlyReadPageUnit(ToolsUnitTests):
    """The suite every LangChain tool integration is expected to pass."""

    @property
    def tool_constructor(self) -> type[PrintFriendlyReadPage]:
        return PrintFriendlyReadPage

    @property
    def tool_constructor_params(self) -> dict[str, Any]:
        return {"api_key": TEST_KEY}

    @property
    def tool_invoke_params_example(self) -> dict[str, Any]:
        return {"url": PAGE}

    @property
    def init_from_env_params(
        self,
    ) -> tuple[dict[str, str], dict[str, Any], dict[str, Any]]:
        return (
            {"PRINTFRIENDLY_API_KEY": "key-from-env"},
            {},
            {"api_key": "key-from-env"},
        )


def tool(**kwargs: Any) -> PrintFriendlyReadPage:
    kwargs.setdefault("api_key", TEST_KEY)
    return PrintFriendlyReadPage(**kwargs)


def test_is_a_base_tool_with_a_stable_name() -> None:
    instance = tool()
    assert isinstance(instance, BaseTool)
    assert instance.name == "printfriendly_read_page"
    assert instance.args == {
        "url": {
            "description": instance.args["url"]["description"],
            "title": "Url",
            "type": "string",
        }
    }


def test_missing_key_fails_at_construction() -> None:
    with pytest.raises(ValueError, match="PRINTFRIENDLY_API_KEY"):
        PrintFriendlyReadPage()


def test_blank_key_fails_at_construction() -> None:
    with pytest.raises(ValueError, match="API key"):
        PrintFriendlyReadPage(api_key="   ")


def test_key_is_not_in_repr() -> None:
    assert TEST_KEY not in repr(tool())
    assert TEST_KEY not in str(tool())


def test_invoke_returns_the_page_text(api: respx.MockRouter) -> None:
    route = api.post("/v2/convert").respond(200, json=success_body())
    result = tool().invoke({"url": PAGE})
    assert result.startswith("# Eclipse")
    sent = json.loads(route.calls.last.request.content)
    assert sent == {"url": PAGE, "output": "markdown", "include_links": False}
    assert route.calls.last.request.headers["Authorization"] == f"Bearer {TEST_KEY}"


def test_options_are_sent(api: respx.MockRouter) -> None:
    route = api.post("/v2/convert").respond(200, json=success_body(output="text"))
    tool(output="text", include_links=True).invoke({"url": PAGE})
    sent = json.loads(route.calls.last.request.content)
    assert sent["output"] == "text"
    assert sent["include_links"] is True


async def test_ainvoke(api: respx.MockRouter) -> None:
    api.post("/v2/convert").respond(200, json=success_body())
    assert (await tool().ainvoke({"url": PAGE})).startswith("# Eclipse")


def test_max_characters_truncates_with_a_notice(api: respx.MockRouter) -> None:
    api.post("/v2/convert").respond(200, json=success_body("x" * 100))
    result = tool(max_characters=10).invoke({"url": PAGE})
    assert result.startswith("x" * 10)
    assert "Truncated" in result
    assert "first 10 of 100 characters" in result


def test_short_pages_are_not_truncated(api: respx.MockRouter) -> None:
    api.post("/v2/convert").respond(200, json=success_body("short"))
    assert tool(max_characters=10).invoke({"url": PAGE}) == "short"


def test_unreadable_page_is_handed_back_to_the_model_as_text(
    api: respx.MockRouter,
) -> None:
    api.post("/v2/convert").respond(
        422,
        json=generation_error(
            "content_blocked", "Blocked by the site", retryable=False
        ),
    )
    result = tool().invoke({"url": PAGE})
    assert "could not read the page" in result
    assert "content_blocked" in result
    assert PAGE in result


def test_unreadable_page_raises_tool_exception_when_not_handled(
    api: respx.MockRouter,
) -> None:
    api.post("/v2/convert").respond(
        422, json=generation_error("parse_failed", "No article", retryable=False)
    )
    with pytest.raises(ToolException, match="parse_failed"):
        tool(handle_tool_error=False).invoke({"url": PAGE})


def test_bad_key_is_not_hidden_from_the_caller(api: respx.MockRouter) -> None:
    api.post("/v2/convert").respond(
        401,
        json={
            "status": "failed",
            "error": {
                "type": "parameters-validation",
                "errors": {},
                "message": "Bad key",
                "code": "invalid_api_key",
                "retryable": False,
            },
        },
    )
    with pytest.raises(PrintFriendlyError) as info:
        tool().invoke({"url": PAGE})
    assert info.value.code == "invalid_api_key"


async def test_async_bad_key_and_page_errors(api: respx.MockRouter) -> None:
    api.post("/v2/convert").mock(
        side_effect=[
            httpx.Response(
                402, json=generation_error("quota_exceeded", "Used up", retryable=False)
            ),
            httpx.Response(
                422, json=generation_error("fetch_failed", "Gone", retryable=False)
            ),
        ]
    )
    with pytest.raises(PrintFriendlyError) as info:
        await tool().ainvoke({"url": PAGE})
    assert info.value.code == "quota_exceeded"
    assert "fetch_failed" in await tool().ainvoke({"url": PAGE})


def test_bad_url_is_reported_to_the_model_and_costs_no_request(
    api: respx.MockRouter,
) -> None:
    route = api.post("/v2/convert").respond(200, json=success_body())
    result = tool().invoke({"url": "not a url"})
    assert "Not a valid http(s) address" in result
    assert route.call_count == 0


def test_retries_a_rate_limit(api: respx.MockRouter, waits: list[float]) -> None:
    api.post("/v2/convert").mock(
        side_effect=[
            httpx.Response(
                429,
                headers={"Retry-After": "2"},
                json=generation_error("rate_limited", "Slow down", retryable=True),
            ),
            httpx.Response(200, json=success_body()),
        ]
    )
    assert tool().invoke({"url": PAGE}).startswith("# Eclipse")
    assert waits == [2.0]


def test_tool_message_content_for_a_tool_call(api: respx.MockRouter) -> None:
    api.post("/v2/convert").respond(200, json=success_body("hello"))
    message = tool().invoke(
        {
            "name": "printfriendly_read_page",
            "args": {"url": PAGE},
            "id": "1",
            "type": "tool_call",
        }
    )
    assert message.content == "hello"
    assert message.tool_call_id == "1"
