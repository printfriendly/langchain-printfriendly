"""LangChain's standard integration suite for tools, run against a mocked API.

The standard suite invokes the tool four times. Against the real API that is four
documents of a 100 a month free plan on every run, so these run against a mock
that answers the way the API does. `test_live.py` talks to the real API.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
import respx
from langchain_tests.integration_tests import ToolsIntegrationTests

from langchain_printfriendly import PrintFriendlyReadPage
from tests.conftest import BASE_URL, PAGE, TEST_KEY, success_body


class TestPrintFriendlyReadPageIntegration(ToolsIntegrationTests):
    @pytest.fixture(autouse=True)
    def _mock_api(self) -> Iterator[None]:
        with respx.mock(
            base_url=BASE_URL, assert_all_called=False, assert_all_mocked=True
        ) as router:
            router.post("/v2/convert").respond(200, json=success_body())
            yield

    @property
    def tool_constructor(self) -> type[PrintFriendlyReadPage]:
        return PrintFriendlyReadPage

    @property
    def tool_constructor_params(self) -> dict[str, Any]:
        return {"api_key": TEST_KEY}

    @property
    def tool_invoke_params_example(self) -> dict[str, Any]:
        return {"url": PAGE}
