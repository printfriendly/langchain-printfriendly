# LangChain docs listing request (ready to paste)

Do not send this until `langchain-printfriendly` is published on PyPI and the GitHub repository is public. Nothing has been sent.

## What LangChain currently asks for

Sources checked 2026-10-16:

- https://docs.langchain.com/oss/python/contributing/integrations-langchain
- https://docs.langchain.com/oss/python/contributing/publish-langchain
- Issue form: https://github.com/langchain-ai/docs/blob/main/.github/ISSUE_TEMPLATE/06-integration-submission.yml

In short:

1. New integrations are published as standalone PyPI packages named `langchain-<name>`. They are not accepted as pull requests to any `langchain-ai` repository.
2. After publishing, open an "Integration listing" issue in `langchain-ai/docs`. A maintainer applies the `integration-run` label, and automation opens a PR that adds a row to `scripts/data/integration_external_docs.yaml`.
3. Do not open a manual docs PR or add an MDX page. Automation closes those.
4. A hosted guide page needs 50,000 or more monthly PyPI downloads, or maintainers choosing to feature it. Until then the listing links to our own README.

## A risk to know before sending

LangChain's guide lists **Document Loaders** under "Not these" for new integrations, with the reason "High maintenance burden". It lists **Tools/Toolkits** as encouraged. This package ships both, so the safest request names the tool as the primary component and mentions the loader as part of the package. The form has a single "Component type" dropdown, so pick `tools`.

I could not find a statement of what happens to a listing request for a document loader, so whether a `document_loaders` request would be declined is uncertain. Choosing `tools` avoids the question.

## Issue title

```
[integration]: PrintFriendlyReadPage
```

## Form fields

| Field | Value |
| --- | --- |
| Display or class name | `PrintFriendlyReadPage` |
| Language | Python |
| Component type | tools |
| PyPI package name | `langchain-printfriendly` |
| npm package name | (leave blank) |
| Docs URL | `https://github.com/printfriendly/langchain-printfriendly#readme` |
| Source repository | `printfriendly/langchain-printfriendly` |
| Confirmations | tick "The package is already published on PyPI and/or npm." |

### Short provider description

```
Reads a web page through the PrintFriendly API and returns the article as clean Markdown, text or HTML without ads or page clutter. The package also includes a PrintFriendlyLoader document loader.
```

### Capability flags (optional)

Leave blank. The form says these apply to chat models and vector stores.

## If a maintainer asks for the loader to be listed too

Reply on the issue with:

```
The same package also provides PrintFriendlyLoader (langchain_printfriendly.document_loaders), a BaseLoader with lazy_load and alazy_load that returns one Document per URL. Happy to have it listed under document_loaders if that is useful, or tools only if you prefer.
```
