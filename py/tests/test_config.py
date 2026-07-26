import pytest

from iconomics.config import (
    CANONICAL_FIELDS,
    ConfigError,
    find_config_dir,
    load_header_aliases,
)


def test_canonical_fields_are_the_documented_set():
    assert CANONICAL_FIELDS == (
        "date",
        "counterparty",
        "vat_number",
        "description",
        "amount_net",
        "vat_amount",
        "vat_rate",
        "account",
        "currency",
    )


def test_config_dir_is_discovered_from_the_repo():
    assert (find_config_dir() / "headers.yaml").is_file()


def test_aliases_map_normalized_headers_to_canonical_fields():
    aliases = load_header_aliases()
    assert aliases["дата"] == "date"
    assert aliases["контрагент"] == "counterparty"
    assert aliases["партньор"] == "counterparty"
    assert aliases["сума без ддс"] == "amount_net"
    assert aliases["ддс"] == "vat_amount"
    assert aliases["валута"] == "currency"


def test_aliases_are_stored_normalized():
    # Every key must already be normalized, so lookup is a plain dict hit.
    aliases = load_header_aliases()
    assert all(key == key.lower().strip() for key in aliases)


def test_missing_config_dir_is_a_clear_error(tmp_path):
    with pytest.raises(ConfigError, match="headers.yaml"):
        load_header_aliases(tmp_path)


def test_unknown_canonical_field_in_config_is_rejected(tmp_path):
    (tmp_path / "headers.yaml").write_text("not_a_field:\n  - foo\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="not_a_field"):
        load_header_aliases(tmp_path)
