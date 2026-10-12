from transformation.load_dimesions import count_appdetails_languages, parse_owners


def test_parse_owners():
    assert parse_owners("20,000,000 .. 50,000,000") == (20_000_000, 50_000_000)
    assert parse_owners("0 .. 20,000") == (0, 20_000)
    assert parse_owners(None) == (None, None)


def test_count_appdetails_languages():
    html = "English<strong>*</strong>, French, German<strong>*</strong><br><strong>*</strong>languages with full audio support"
    assert count_appdetails_languages(html) == 3
    assert count_appdetails_languages(None) == 0
