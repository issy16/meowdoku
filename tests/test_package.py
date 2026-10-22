import meowdoku


def test_package_imports_with_version() -> None:
    assert meowdoku.__version__ == "0.1.0"
