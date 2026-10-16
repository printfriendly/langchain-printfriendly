"""LangChain integration for the PrintFriendly API."""

from importlib import metadata

from langchain_printfriendly._client import PrintFriendlyError
from langchain_printfriendly.document_loaders import PrintFriendlyLoader
from langchain_printfriendly.tools import PrintFriendlyReadPage

try:
    __version__ = metadata.version(__package__ or "langchain-printfriendly")
except metadata.PackageNotFoundError:  # pragma: no cover - running from source
    __version__ = ""
del metadata

__all__ = [
    "PrintFriendlyError",
    "PrintFriendlyLoader",
    "PrintFriendlyReadPage",
    "__version__",
]
