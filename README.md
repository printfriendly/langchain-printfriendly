# langchain-printfriendly

[LangChain](https://python.langchain.com/) integration for the [PrintFriendly API](https://www.printfriendly.com/api). Give it a web page address and it returns the article as clean Markdown, without ads, menus, cookie banners or other clutter.

It ships two things:

- `PrintFriendlyLoader`, a document loader. One `Document` per URL, with the title, site, author, date, excerpt, image and word count in the metadata.
- `PrintFriendlyReadPage`, a tool that lets an agent read a page it is pointed at.

## Install

```bash
pip install -U langchain-printfriendly
```

## Get an API key

Get a free key at [printfriendly.com/me/api-key](https://www.printfriendly.com/me/api-key). The free plan includes 100 documents a month and needs no card. Paid plans include more.

```bash
export PRINTFRIENDLY_API_KEY="your key"
```

Or pass it in code with `api_key="..."`.

To check that a key works without using a document, call the free usage endpoint. It is never counted:

```bash
curl -H "Authorization: Bearer $PRINTFRIENDLY_API_KEY" https://api.printfriendly.com/v2/usage
```

## Load pages

```python
from langchain_printfriendly import PrintFriendlyLoader

loader = PrintFriendlyLoader(
    [
        "https://en.wikipedia.org/wiki/Eclipse",
        "https://en.wikipedia.org/wiki/Solar_eclipse",
    ]
)
docs = loader.load()

print(docs[0].page_content[:200])
print(docs[0].metadata)
# {'source': 'https://en.wikipedia.org/wiki/Eclipse',
#  'title': 'Eclipse',
#  'site': 'en.wikipedia.org',
#  'word_count': 6120}
```

Load lazily, one page at a time:

```python
for doc in loader.lazy_load():
    print(doc.metadata["title"])
```

Or asynchronously (uses `httpx.AsyncClient`):

```python
docs = [doc async for doc in loader.alazy_load()]
docs = await loader.aload()
```

Pages are read one after another, in the order you gave them.

### Options

| Argument | Default | What it does |
| --- | --- | --- |
| `urls` | required | One URL or a list of them. Each must be an `http` or `https` address. |
| `api_key` | `$PRINTFRIENDLY_API_KEY` | Your API key. |
| `output` | `"markdown"` | `"markdown"`, `"text"` or `"html"`. |
| `include_links` | `False` | Keep link and image addresses in Markdown and text. Off by default: links keep their words and lose their addresses. |
| `timeout` | `60` | Seconds to wait for each response. The API answers within 27 seconds. |
| `max_retries` | `2` | Retries after a rate limit, a dropped connection or an error the API marks `retryable`. `0` turns retries off. |
| `continue_on_failure` | `False` | Skip a page that cannot be read, with a logged warning, instead of raising. |
| `base_url` | `https://api.printfriendly.com` | Only change this for testing. |

### Metadata

| Key | Meaning |
| --- | --- |
| `source` | The URL you passed in. |
| `title` | The page title. |
| `site` | The host name of the page. |
| `author` | The author, when the page names one. |
| `date` | The publish date as ISO 8601, when known. |
| `excerpt` | A short summary of the page. |
| `image` | The main image of the article. |
| `word_count` | Words in the extracted article. |

A field the page does not have is left out, not set to `None`.

## Use it as an agent tool

```python
from langchain.agents import create_agent
from langchain_printfriendly import PrintFriendlyReadPage

tool = PrintFriendlyReadPage()  # reads PRINTFRIENDLY_API_KEY
agent = create_agent(your_chat_model, tools=[tool])

agent.invoke(
    {"messages": [("user", "Summarize https://en.wikipedia.org/wiki/Eclipse")]}
)
```

`your_chat_model` is any LangChain chat model that supports tool calling.

You can also call the tool directly:

```python
tool.invoke({"url": "https://en.wikipedia.org/wiki/Eclipse"})
```

The tool takes the same `output`, `include_links`, `timeout`, `max_retries` and `base_url` options as the loader. It adds `max_characters`, which cuts long pages so they do not fill the model's context window. A page that cannot be read comes back to the model as text, so it can try something else.

## Use it in a RAG pipeline

```python
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter

docs = PrintFriendlyLoader(urls).load()
chunks = RecursiveCharacterTextSplitter(
    chunk_size=1000, chunk_overlap=100
).split_documents(docs)
store = InMemoryVectorStore.from_documents(chunks, embedding=your_embeddings)
retriever = store.as_retriever()
```

The metadata travels with each chunk, so you can cite `source` and `title` in answers.

## Errors, retries and limits

Every failure raises `PrintFriendlyError`:

```python
from langchain_printfriendly import PrintFriendlyError

try:
    docs = PrintFriendlyLoader(urls).load()
except PrintFriendlyError as error:
    print(error.code)  # for example "fetch_failed" or "quota_exceeded"
    print(error.retryable)  # whether trying again can work
    print(error.request_id)  # quote this to PrintFriendly support
```

- **Rate limits.** Free keys allow 10 requests a minute. On a `429` the loader waits for the time in `Retry-After` and tries again, up to `max_retries` times. If the API asks for more than 60 seconds, the loader raises instead of blocking.
- **Retryable errors.** Errors the API marks `retryable` (a page that timed out, for example) are retried with a short backoff, up to `max_retries` times. A dropped connection is retried too. A read timeout is not, because the document may already have been counted.
- **Everything else raises at once**, with the API's error code and message: `invalid_parameters`, `fetch_failed`, `parse_failed`, `content_blocked`, `render_failed` and so on.
- **`continue_on_failure=True`** skips pages that fail one by one. Key and plan errors (`api_key_required`, `invalid_api_key`, `subscription_inactive`, `limit_exceeded`, `quota_exceeded`) still raise, because every later page would fail the same way.
- **Billing.** Only a successful read counts as a document on your plan. Failed reads are free. The plan limit comes back as `quota_exceeded` with an `upgrade_url`.

See the [API reference](https://www.printfriendly.com/openapi.json) for every code.

## Development

The project uses [uv](https://docs.astral.sh/uv/).

```bash
make test               # unit tests, no network
make integration_test   # LangChain's standard tool suite, against a mocked API
make lint               # ruff, mypy, codespell
```

The unit tests mock the HTTP layer with [respx](https://lundberg.github.io/respx/) and include LangChain's `ToolsUnitTests` suite from `langchain-tests`. LangChain does not publish a standard test suite for document loaders, so the loader has its own tests.

`make live_test` calls the real API. It needs `PRINTFRIENDLY_API_KEY` and reads two pages, which is two documents of your plan. Without the key it is skipped.

## Links

- [PrintFriendly API](https://www.printfriendly.com/api)
- [API reference (OpenAPI)](https://www.printfriendly.com/openapi.json)
- [Support](https://www.printfriendly.com/support)

## License

MIT. See [LICENSE](LICENSE).
