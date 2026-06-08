import pytest


@pytest.mark.xfail(reason="known issue")
def test_xfail_no_strict():
    raise AssertionError
