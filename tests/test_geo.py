import pytest

from job_hunter.sources.geo import infer_nigeria_eligible_from_restrictions, infer_nigeria_eligible_from_text


@pytest.mark.parametrize(
    ("location", "default_when_specific", "expected"),
    [
        ("Worldwide", False, True),
        ("Anywhere", None, True),
        ("Nigeria", False, True),
        ("Africa (Remote)", None, True),
        ("USA Only", False, False),
        ("Germany", False, False),
        ("Germany", None, None),
        ("", False, None),
        ("", None, None),
        (None, False, None),
    ],
)
def test_infer_nigeria_eligible_from_text(location, default_when_specific, expected):
    assert infer_nigeria_eligible_from_text(location, default_when_specific=default_when_specific) is expected


@pytest.mark.parametrize(
    ("restrictions", "expected"),
    [
        (None, None),
        ([], True),
        (["United States"], False),
        (["Worldwide"], True),
        (["Nigeria", "Ghana"], True),
    ],
)
def test_infer_nigeria_eligible_from_restrictions(restrictions, expected):
    assert infer_nigeria_eligible_from_restrictions(restrictions) is expected
