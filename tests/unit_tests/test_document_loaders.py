from __future__ import annotations

import json
import logging
from collections.abc import Generator

import httpx
import pytest
import respx
from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document

from langchain_printfriendly import PrintFriendlyError, PrintFriendlyLoader
from tests.conftest import PAGE, TEST_KEY, generation_error, success_body

OTHER = "https://example.org/post/1"
THIRD = "https://example.net/post/2"


def loader(urls: object = PAGE, **kwargs: object) -> PrintFriendlyLoader:
    kwargs.setdefault("api_key", TEST_KEY)
    return PrintFriendlyLoader(urls, **kwargs)  # type: ignore[arg-type]


def test_is_a_base_loader() -> None:
    assert isinstance(loader(), BaseLoader)


def test_load_returns_one_document_per_url(api: respx.MockRouter) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        url = json.loads(request.content)["url"]
        return httpx.Response(
            200, json=success_body(f"# Page\n\ntext for {url}", url=url, title=url[-6:])
        )

    api.post("/v2/convert").mock(side_effect=handler)
    docs = loader([PAGE, OTHER]).load()
    assert [type(d) for d in docs] == [Document, Document]
    assert docs[0].page_content == f"# Page\n\ntext for {PAGE}"
    assert docs[0].metadata["source"] == PAGE
    assert docs[1].metadata["source"] == OTHER
    assert docs[1].metadata["title"] == OTHER[-6:]


def test_metadata_fields(api: respx.MockRouter) -> None:
    api.post("/v2/convert").respond(
        200,
        json=success_body(
            author="Ada",
            date="2026-01-02",
            excerpt="An excerpt.",
            image="https://img.test/a.png",
        ),
    )
    (doc,) = loader().load()
    assert doc.metadata == {
        "source": PAGE,
        "title": "Eclipse",
        "site": "en.wikipedia.org",
        "author": "Ada",
        "date": "2026-01-02",
        "excerpt": "An excerpt.",
        "image": "https://img.test/a.png",
        "word_count": 7,
    }


def test_options_are_sent_to_the_api(api: respx.MockRouter) -> None:
    route = api.post("/v2/convert").respond(200, json=success_body(output="html"))
    loader(output="html", include_links=True).load()
    sent = json.loads(route.calls.last.request.content)
    assert sent == {"url": PAGE, "output": "html", "include_links": True}


def test_single_string_url_is_accepted() -> None:
    assert loader("https://a.test/x").urls == ["https://a.test/x"]


def test_defaults_to_markdown_without_links(api: respx.MockRouter) -> None:
    route = api.post("/v2/convert").respond(200, json=success_body())
    loader().load()
    sent = json.loads(route.calls.last.request.content)
    assert sent["output"] == "markdown"
    assert sent["include_links"] is False


def test_api_key_comes_from_the_environment(
    api: respx.MockRouter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PRINTFRIENDLY_API_KEY", "env-key")
    route = api.post("/v2/convert").respond(200, json=success_body())
    PrintFriendlyLoader(PAGE).load()
    assert route.calls.last.request.headers["Authorization"] == "Bearer env-key"


def test_explicit_key_beats_the_environment(
    api: respx.MockRouter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PRINTFRIENDLY_API_KEY", "env-key")
    route = api.post("/v2/convert").respond(200, json=success_body())
    PrintFriendlyLoader(PAGE, api_key="arg-key").load()
    assert route.calls.last.request.headers["Authorization"] == "Bearer arg-key"


def test_missing_key_fails_at_construction() -> None:
    with pytest.raises(ValueError, match="PRINTFRIENDLY_API_KEY"):
        PrintFriendlyLoader(PAGE)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"output": "pdf"},
        {"timeout": 0},
        {"max_retries": -1},
    ],
)
def test_bad_options_fail_at_construction(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        loader(**kwargs)


def test_bad_url_fails_at_construction() -> None:
    with pytest.raises(ValueError, match="not-a-url"):
        loader(["https://ok.test/x", "not-a-url"])


def test_repr_does_not_show_the_key() -> None:
    assert TEST_KEY not in repr(loader())
    assert "PrintFriendlyLoader" in repr(loader())


def test_lazy_load_reads_one_page_at_a_time(api: respx.MockRouter) -> None:
    route = api.post("/v2/convert").respond(200, json=success_body())
    iterator = loader([PAGE, OTHER, THIRD]).lazy_load()
    assert isinstance(iterator, Generator)
    assert route.call_count == 0
    next(iterator)
    assert route.call_count == 1
    next(iterator)
    assert route.call_count == 2
    iterator.close()
    assert route.call_count == 2


def test_failure_raises_by_default(api: respx.MockRouter) -> None:
    api.post("/v2/convert").respond(
        422, json=generation_error("parse_failed", "No article here", retryable=False)
    )
    with pytest.raises(PrintFriendlyError, match="No article here") as info:
        loader().load()
    assert info.value.url == PAGE


def test_continue_on_failure_skips_the_bad_page_and_logs(
    api: respx.MockRouter, caplog: pytest.LogCaptureFixture
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        url = json.loads(request.content)["url"]
        if url == OTHER:
            return httpx.Response(
                422, json=generation_error("fetch_failed", "Gone", retryable=False)
            )
        return httpx.Response(200, json=success_body(url=url))

    api.post("/v2/convert").mock(side_effect=handler)
    with caplog.at_level(logging.WARNING, logger="langchain_printfriendly"):
        docs = loader([PAGE, OTHER, THIRD], continue_on_failure=True).load()
    assert [d.metadata["source"] for d in docs] == [PAGE, THIRD]
    assert any(OTHER in record.getMessage() for record in caplog.records)


def test_continue_on_failure_still_raises_for_a_bad_key(api: respx.MockRouter) -> None:
    route = api.post("/v2/convert").respond(
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
        loader([PAGE, OTHER], continue_on_failure=True).load()
    assert info.value.code == "invalid_api_key"
    assert route.call_count == 1  # it did not carry on to the second page


def test_continue_on_failure_still_raises_when_quota_is_used_up(
    api: respx.MockRouter,
) -> None:
    api.post("/v2/convert").respond(
        402, json=generation_error("quota_exceeded", "Used up", retryable=False)
    )
    with pytest.raises(PrintFriendlyError) as info:
        loader([PAGE, OTHER], continue_on_failure=True).load()
    assert info.value.code == "quota_exceeded"


def test_rate_limit_is_waited_out_between_pages(
    api: respx.MockRouter, waits: list[float]
) -> None:
    api.post("/v2/convert").mock(
        side_effect=[
            httpx.Response(200, json=success_body()),
            httpx.Response(
                429,
                headers={"Retry-After": "5"},
                json=generation_error("rate_limited", "Slow down", retryable=True),
            ),
            httpx.Response(200, json=success_body()),
        ]
    )
    docs = loader([PAGE, OTHER]).load()
    assert len(docs) == 2
    assert waits == [5.0]


def test_max_retries_is_passed_through(api: respx.MockRouter) -> None:
    route = api.post("/v2/convert").respond(
        422, json=generation_error("fetch_failed", "Timed out", retryable=True)
    )
    with pytest.raises(PrintFriendlyError):
        loader(max_retries=0).load()
    assert route.call_count == 1


async def test_alazy_load(api: respx.MockRouter) -> None:
    api.post("/v2/convert").respond(200, json=success_body())
    docs = [doc async for doc in loader([PAGE, OTHER]).alazy_load()]
    assert [d.metadata["source"] for d in docs] == [PAGE, OTHER]
    assert all(isinstance(d, Document) for d in docs)


async def test_aload_uses_the_async_path(api: respx.MockRouter) -> None:
    api.post("/v2/convert").respond(200, json=success_body())
    docs = await loader().aload()
    assert len(docs) == 1


async def test_async_continue_on_failure_and_account_errors(
    api: respx.MockRouter,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        url = json.loads(request.content)["url"]
        if url == OTHER:
            return httpx.Response(
                422, json=generation_error("fetch_failed", "Gone", retryable=False)
            )
        return httpx.Response(200, json=success_body(url=url))

    api.post("/v2/convert").mock(side_effect=handler)
    docs = [
        d
        async for d in loader(
            [PAGE, OTHER, THIRD], continue_on_failure=True
        ).alazy_load()
    ]
    assert [d.metadata["source"] for d in docs] == [PAGE, THIRD]

    with pytest.raises(PrintFriendlyError):
        [d async for d in loader([PAGE, OTHER]).alazy_load()]


async def test_async_retry_on_rate_limit(
    api: respx.MockRouter, waits: list[float]
) -> None:
    api.post("/v2/convert").mock(
        side_effect=[
            httpx.Response(
                429,
                headers={"Retry-After": "3"},
                json=generation_error("rate_limited", "Slow down", retryable=True),
            ),
            httpx.Response(200, json=success_body()),
        ]
    )
    docs = await loader().aload()
    assert len(docs) == 1
    assert waits == [3.0]


async def test_async_options_are_sent_to_the_api(api: respx.MockRouter) -> None:
    route = api.post("/v2/convert").respond(200, json=success_body(output="text"))
    docs = [d async for d in loader(output="text", include_links=True).alazy_load()]
    assert len(docs) == 1
    sent = json.loads(route.calls.last.request.content)
    assert sent == {"url": PAGE, "output": "text", "include_links": True}
