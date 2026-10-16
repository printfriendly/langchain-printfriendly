# Changelog

## 0.1.0

First release.

- `PrintFriendlyLoader`: a LangChain document loader. One `Document` per URL, as Markdown, text or HTML. `lazy_load` and `alazy_load`.
- `PrintFriendlyReadPage`: a LangChain tool that reads a page for an agent.
- Waits out `429` responses (honoring `Retry-After`) and retries errors the API marks `retryable`, a bounded number of times.
- `continue_on_failure` skips a page that cannot be read. Key and plan errors always raise.
