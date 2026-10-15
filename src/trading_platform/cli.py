"""Offline scaffold inspection. No broker access or execution commands."""
import argparse
import json
from pathlib import Path


def validate_config(data):
    if not isinstance(data, dict):
        raise ValueError("configuration must be an object")
    required = {"schema_version", "instance_id", "strategy", "mode", "universe"}
    if set(data) != required:
        raise ValueError("configuration must contain exactly: " + ", ".join(sorted(required)))
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ValueError("schema_version must be integer 1")
    for key in ("instance_id", "strategy"):
        if not isinstance(data[key], str) or not data[key].strip():
            raise ValueError(f"{key} must be a non-empty string")
    if data["mode"] != "paper":
        raise ValueError("this scaffold supports paper configuration only")
    universe = data["universe"]
    if not isinstance(universe, list) or not universe or any(
        not isinstance(item, str) or not item.strip() for item in universe
    ):
        raise ValueError("universe must be a non-empty list of instrument names")
    if len(set(universe)) != len(universe):
        raise ValueError("universe must not contain duplicates")
    return {"valid": True, "instance_id": data["instance_id"],
            "mode": "paper", "runtime_implemented": False,
            "note": "Shape validation only; strategy loading and trading are not implemented."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="show scaffold capabilities")
    validate = sub.add_parser("validate-config", help="validate an offline example configuration")
    validate.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    if args.command == "status":
        print(json.dumps({"stage": "scaffold", "trading_enabled": False}))
        return 0
    try:
        result = validate_config(json.loads(args.path.read_text()))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))
    return 0
