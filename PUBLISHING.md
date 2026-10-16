# Publishing

How to get `langchain-printfriendly` onto PyPI and listed in the LangChain docs. Steps 1 to 3 happen once. After that, a release is one tag.

Nothing here has been done yet. The repository is private, nothing is on PyPI, and nothing has been sent to LangChain.

## Before you start

- The package name `langchain-printfriendly` was free on PyPI on 2026-10-16. A pending publisher does not reserve it, so do steps 2 and 3 soon after each other.
- You need a PyPI account with a verified email and two-factor authentication.
- The repository can stay private for the PyPI release. It must be public before you ask LangChain to list it, because the listing links to the README and the source.

## 1. Make the repository public (when ready)

On GitHub: `printfriendly/langchain-printfriendly` > Settings > General > Danger Zone > Change visibility > Make public.

Trusted publishing works from a private repository. Public is needed for the LangChain listing and for the package page to link to its source.

## 2. Add a pending trusted publisher on PyPI (once)

A pending publisher lets the first release create the project, so no manual first upload is needed.

1. Sign in to pypi.org. Open your **account** Publishing page (account sidebar, not a project page, because the project does not exist yet).
2. Under **Add a new pending publisher**, choose **GitHub** and fill in:
   - PyPI project name: `langchain-printfriendly`
   - Owner: `printfriendly`
   - Repository name: `langchain-printfriendly`
   - Workflow name: `publish.yml`
   - Environment name: `pypi`
3. Save.

Docs: https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/

## 3. Create the GitHub environment (once)

The workflow's publish job uses an environment named `pypi`. In the repository: Settings > Environments > New environment > `pypi`. Optionally add yourself as a required reviewer so every release waits for your click.

## 4. Release

```sh
# 1. Set `version` in pyproject.toml, add the changes to CHANGELOG.md, commit, merge to main.
# 2. Tag the release. The tag must be v<version> exactly.
git tag v0.1.0
git push origin v0.1.0
```

`.github/workflows/publish.yml` checks that the tag matches `pyproject.toml`, runs lint and the tests, builds, and publishes with PyPI trusted publishing. Watch it on the Actions tab. If the tag and the version differ, the run stops before it builds.

Afterwards, check https://pypi.org/project/langchain-printfriendly/ and run `pip install langchain-printfriendly` in a clean environment.

## 5. Ask LangChain to list it

Read `docs/upstream/langchain-docs-listing-issue.md`. LangChain does not take integrations as pull requests. The listing is an issue on `langchain-ai/docs` using their "Integration listing" form; a maintainer applies a label and automation opens the docs PR.

Do it after the package is on PyPI and the repository is public.
