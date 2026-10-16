"""Document loader that reads web pages through the PrintFriendly API."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Iterator, Sequence

from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document

from langchain_printfriendly._client import (
    DEFAULT_BASE_URL,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
    Page,
    PrintFriendlyClient,
    PrintFriendlyError,
    TextOutput,
    resolve_api_key,
    validate_output,
    validate_urls,
)

logger = logging.getLogger(__name__)


class PrintFriendlyLoader(BaseLoader):
    """Load web pages as clean, ad-free text with the PrintFriendly API.

    PrintFriendly fetches each page, keeps the article and drops ads,
    navigation, cookie banners and other clutter. Each URL becomes one
    `Document`.

    Setup:
        Install the package and get a free API key (100 documents a month) at
        https://www.printfriendly.com/me/api-key, then set it:

        ```bash
        pip install -U langchain-printfriendly
        export PRINTFRIENDLY_API_KEY="..."
        ```

    Instantiate:
        ```python
        from langchain_printfriendly import PrintFriendlyLoader

        loader = PrintFriendlyLoader(
            ["https://en.wikipedia.org/wiki/Eclipse"],
            output="markdown",
            include_links=False,
        )
        ```

    Load:
        ```python
        docs = loader.load()
        docs[0].page_content[:100]
        docs[0].metadata
        # {'source': 'https://en.wikipedia.org/wiki/Eclipse',
        #  'title': 'Eclipse - Wikipedia', 'site': 'en.wikipedia.org',
        #  'author': 'Contributors to Wikimedia projects', 'date': '2001-11-02',
        #  'excerpt': '...', 'image': '...', 'word_count': 5097}
        ```

    Lazy load:
        ```python
        for doc in loader.lazy_load():
            ...
        ```

    Async load:
        ```python
        docs = [doc async for doc in loader.alazy_load()]
        ```

    Pages are read one at a time and in the order given. A free key allows 10
    requests a minute; when the API answers 429 the loader waits for the time
    in ``Retry-After`` and tries again, up to ``max_retries`` times.

    Only a successful read counts as a document on your plan. Failed reads are
    free.

    Metadata:
        ``source`` is the URL you passed in. ``title``, ``site``, ``author``,
        ``date``, ``excerpt``, ``image`` and ``word_count`` come from the page.
        Fields the page does not have are left out.
    """

    def __init__(
        self,
        urls: str | Sequence[str],
        *,
        api_key: str | None = None,
        output: TextOutput = "markdown",
        include_links: bool = False,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        continue_on_failure: bool = False,
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        """Create a loader.

        Args:
            urls: One or more http(s) page addresses.
            api_key: PrintFriendly API key. Defaults to the
                ``PRINTFRIENDLY_API_KEY`` environment variable.
            output: ``"markdown"`` (default), ``"text"`` or ``"html"``.
            include_links: Keep link and image addresses in markdown and text
                output. Off by default: links keep their words and lose their
                addresses.
            timeout: Seconds to wait for each response. The API answers within
                27 seconds, so the default is 60.
            max_retries: How many times to retry a request after a rate limit,
                a connection failure or an error the API marks ``retryable``.
                Set 0 to never retry.
            continue_on_failure: If True, log a warning and skip a page that
                cannot be read instead of raising. Key and plan errors
                (``invalid_api_key``, ``quota_exceeded`` and the like) always
                raise, because every later page would fail the same way.
            base_url: API base URL. Change only for testing.

        Raises:
            ValueError: If the key is missing, a URL is not http(s), or an
                option is out of range.
        """
        if timeout <= 0:
            raise ValueError("timeout must be greater than 0.")
        if max_retries < 0:
            raise ValueError("max_retries must be 0 or more.")
        self.urls: list[str] = validate_urls(urls)
        self.output: TextOutput = validate_output(output)
        self.include_links = include_links
        self.timeout = timeout
        self.max_retries = max_retries
        self.continue_on_failure = continue_on_failure
        self.base_url = base_url
        self._api_key = resolve_api_key(api_key)

    def __repr__(self) -> str:
        """Show the settings without the API key."""
        return (
            f"{type(self).__name__}(urls={self.urls!r}, output={self.output!r}, "
            f"include_links={self.include_links!r})"
        )

    def _client(self) -> PrintFriendlyClient:
        return PrintFriendlyClient(
            self._api_key,
            base_url=self.base_url,
            timeout=self.timeout,
            max_retries=self.max_retries,
        )

    def _should_skip(self, error: PrintFriendlyError, url: str) -> bool:
        if self.continue_on_failure and not error.is_account_error:
            logger.warning("Skipping %s: %s", url, error)
            return True
        return False

    @staticmethod
    def _to_document(page: Page) -> Document:
        return Document(page_content=page.content, metadata=dict(page.metadata))

    def lazy_load(self) -> Iterator[Document]:
        """Read the pages one at a time, yielding a `Document` for each.

        Raises:
            PrintFriendlyError: If a page cannot be read and
                ``continue_on_failure`` is False, or on any key or plan error.
        """
        with self._client() as client:
            for url in self.urls:
                try:
                    page = client.convert(
                        url, output=self.output, include_links=self.include_links
                    )
                except PrintFriendlyError as error:
                    if self._should_skip(error, url):
                        continue
                    raise
                yield self._to_document(page)

    async def alazy_load(self) -> AsyncIterator[Document]:
        """Async version of `lazy_load`, using ``httpx.AsyncClient``."""
        async with self._client() as client:
            for url in self.urls:
                try:
                    page = await client.aconvert(
                        url, output=self.output, include_links=self.include_links
                    )
                except PrintFriendlyError as error:
                    if self._should_skip(error, url):
                        continue
                    raise
                yield self._to_document(page)
