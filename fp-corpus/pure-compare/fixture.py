def make_value() -> int:
    return 1


def test_purity():
    assert make_value() == make_value()
