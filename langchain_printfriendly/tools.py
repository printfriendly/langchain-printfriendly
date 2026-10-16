"""Agent tool that reads a web page through the PrintFriendly API."""

from __future__ import annotations

from typing import Any

from langchain_core.callbacks import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain_core.tools import BaseTool, ToolException
from langchain_core.utils import secret_from_env
from pydantic import BaseModel, Field, SecretStr, field_validator

from langchain_printfriendly._client import (
    API_KEY_ENV_VAR,
    DEFAULT_BASE_URL,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
    Page,
    PrintFriendlyClient,
    PrintFriendlyError,
    TextOutput,
    validate_urls,
)


class PrintFriendlyReadPageInput(BaseModel):
    """Input for `PrintFriendlyReadPage`."""

    url: str = Field(
        description="The full http(s) address of the web page to read, "
        "for example https://example.com/article."
    )


class PrintFriendlyReadPage(BaseTool):
    """Read a web page and return its main content as clean text.

    Hand an agent this tool when it needs to read a specific page. PrintFriendly
    fetches the page and removes ads, navigation and other clutter, so the model
    sees the article and not the page chrome.

    Setup:
        ```bash
        pip install -U langchain-printfriendly
        export PRINTFRIENDLY_API_KEY="..."   # free key: printfriendly.com/me/api-key
        ```

    Instantiate:
        ```python
        from langchain_printfriendly import PrintFriendlyReadPage

        tool = PrintFriendlyReadPage()
        ```

    Invoke:
        ```python
        tool.invoke({"url": "https://en.wikipedia.org/wiki/Eclipse"})
        ```

    A page that cannot be read (blocked, not found, timed out) raises a
    `ToolException`, which LangChain hands back to the model as text so it can
    try something else. Key and plan errors raise `PrintFriendlyError` instead,
    because the model cannot fix them.
    """

    name: str = "printfriendly_read_page"
    description: str = (
        "Read a web page and return its main content as clean text, without "
        "ads, menus or other clutter. Input is the full URL of the page. Use "
        "it when you need what a specific page says."
    )
    args_schema: type[BaseModel] = PrintFriendlyReadPageInput
    handle_tool_error: bool = True

    api_key: SecretStr = Field(
        default_factory=secret_from_env(API_KEY_ENV_VAR),
    )
    """PrintFriendly API key. Defaults to the ``PRINTFRIENDLY_API_KEY`` variable."""

    output: TextOutput = "markdown"
    """``"markdown"`` (default), ``"text"`` or ``"html"``."""

    include_links: bool = False
    """Keep link and image addresses in markdown and text output."""

    max_characters: int | None = Field(default=None, ge=1)
    """Cut the returned text to this many characters. None keeps all of it."""

    timeout: float = Field(default=DEFAULT_TIMEOUT, gt=0)
    """Seconds to wait for each response."""

    max_retries: int = Field(default=DEFAULT_MAX_RETRIES, ge=0)
    """Retries after a rate limit, a connection failure or a retryable error."""

    base_url: str = DEFAULT_BASE_URL
    """API base URL. Change only for testing."""

    @field_validator("api_key")
    @classmethod
    def _api_key_not_blank(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError(
                f"A PrintFriendly API key is required. Pass api_key=... or set "
                f"{API_KEY_ENV_VAR}."
            )
        return value

    def _client(self) -> PrintFriendlyClient:
        return PrintFriendlyClient(
            self.api_key.get_secret_value().strip(),
            base_url=self.base_url,
            timeout=self.timeout,
            max_retries=self.max_retries,
        )

    def _format(self, page: Page) -> str:
        text = page.content
        if self.max_characters is not None and len(text) > self.max_characters:
            shown = text[: self.max_characters].rstrip()
            return (
                f"{shown}\n\n[Truncated: showing the first {self.max_characters} "
                f"of {len(text)} characters.]"
            )
        return text

    @staticmethod
    def _as_tool_exception(error: PrintFriendlyError) -> ToolException:
        return ToolException(f"PrintFriendly could not read the page. {error}")

    @staticmethod
    def _checked_url(url: str) -> str:
        try:
            (checked,) = validate_urls(url)
        except ValueError as error:
            raise ToolException(str(error)) from error
        return checked

    def _run(
        self,
        url: str,
        run_manager: CallbackManagerForToolRun | None = None,
        **kwargs: Any,
    ) -> str:
        checked = self._checked_url(url)
        try:
            with self._client() as client:
                page = client.convert(
                    checked, output=self.output, include_links=self.include_links
                )
        except PrintFriendlyError as error:
            if error.is_account_error:
                raise
            raise self._as_tool_exception(error) from error
        return self._format(page)

    async def _arun(
        self,
        url: str,
        run_manager: AsyncCallbackManagerForToolRun | None = None,
        **kwargs: Any,
    ) -> str:
        checked = self._checked_url(url)
        try:
            async with self._client() as client:
                page = await client.aconvert(
                    checked, output=self.output, include_links=self.include_links
                )
        except PrintFriendlyError as error:
            if error.is_account_error:
                raise
            raise self._as_tool_exception(error) from error
        return self._format(page)
