import pytest


@pytest.mark.xfail(strict=True, reason="known issue")
def test_xfail_strict():
    raise AssertionError
