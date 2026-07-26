"""Loads the YAML rule files that keep accounting rules out of the source."""

from pathlib import Path

import yaml

from iconomics.parsing import normalize_header

CANONICAL_FIELDS = (
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


class ConfigError(RuntimeError):
    """Raised when a config file is missing or malformed."""


def find_config_dir() -> Path:
    """Walk up from this module until a directory containing config/ is found."""
    for candidate in Path(__file__).resolve().parents:
        config_dir = candidate / "config"
        if (config_dir / "headers.yaml").is_file():
            return config_dir
    raise ConfigError("could not locate config/headers.yaml above this module")


def load_header_aliases(config_dir: Path | None = None) -> dict[str, str]:
    """Return a mapping of normalized input header -> canonical field name."""
    directory = config_dir if config_dir is not None else find_config_dir()
    path = Path(directory) / "headers.yaml"
    if not path.is_file():
        raise ConfigError(f"missing config file: {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    aliases: dict[str, str] = {}
    for field, values in raw.items():
        if field not in CANONICAL_FIELDS:
            raise ConfigError(
                f"unknown canonical field {field!r} in {path}; "
                f"expected one of {', '.join(CANONICAL_FIELDS)}"
            )
        for value in values or []:
            aliases[normalize_header(value)] = field
    return aliases
