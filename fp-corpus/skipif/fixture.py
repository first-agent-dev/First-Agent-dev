import pytest
import shutil


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_bash_only():
    pass
