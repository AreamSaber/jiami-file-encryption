"""Reject retired security claims instead of silently accepting ineffective flags."""

import copy
import json
from pathlib import Path

import jsonschema
import pytest


ROOT = Path(__file__).resolve().parents[2]
SETTINGS = json.loads((ROOT / "config/security_settings.json").read_text(encoding="utf-8"))
SCHEMA = json.loads((ROOT / "config/schemas/security_settings.schema.json").read_text(encoding="utf-8"))


def test_shipped_security_settings_validate():
    jsonschema.Draft7Validator.check_schema(SCHEMA)
    jsonschema.validate(SETTINGS, SCHEMA)


@pytest.mark.parametrize("algorithm", ["PBKDF2", "Argon2", "scrypt"])
def test_unimplemented_password_derivation_is_rejected(algorithm):
    config = copy.deepcopy(SETTINGS)
    config["security_settings"]["key_management"]["key_derivation"] = {"algorithm": algorithm}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(config, SCHEMA)


def test_removed_environment_checks_are_rejected():
    config = copy.deepcopy(SETTINGS)
    config["security_settings"]["anti_reverse_engineering"] = {"anti_debug": {"enabled": True}}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(config, SCHEMA)
