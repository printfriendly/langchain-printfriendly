from langchain_printfriendly import __all__

EXPECTED_ALL = [
    "PrintFriendlyError",
    "PrintFriendlyLoader",
    "PrintFriendlyReadPage",
    "__version__",
]


def test_all_imports() -> None:
    assert sorted(EXPECTED_ALL) == sorted(__all__)


def test_version_is_set() -> None:
    import langchain_printfriendly

    assert langchain_printfriendly.__version__
