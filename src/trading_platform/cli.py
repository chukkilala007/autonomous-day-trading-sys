"""Strategy validation, causal replay and persistent paper simulation."""
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
    control = sub.add_parser('control',help='submit an audited operator request')
    control.add_argument('action',choices=['pause','resume','flatten'])
    for flag in ('url','token-file','id'): control.add_argument('--'+flag,required=True)
    replay = sub.add_parser("replay", help="offline causal decision replay")
    for flag in ("config", "registry", "input", "output"):
        replay.add_argument("--"+flag, required=True)
    instance = sub.add_parser("validate-instance", help="validate versioned deployment mandate")
    instance.add_argument("path", type=Path)
    status = sub.add_parser("status", help="show capabilities or persisted paper state")
    status.add_argument("--state", type=Path)
    paper=sub.add_parser("run-paper",help="run durable paper simulation only")
    paper.add_argument("--deployment",required=True)
    paper.add_argument("--input",required=True)
    paper.add_argument("--state",required=True)
    paper.add_argument("--once",action="store_true")
    paper.add_argument("--step-delay",type=float,default=0)
    validate = sub.add_parser("validate-config", help="validate an offline example configuration")
    validate.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    if args.command == 'control':
        from .api.control_cli import control
        print(json.dumps(control(args.url,args.token_file,args.id,args.action)))
        return 0
    if args.command == "run-paper":
        from .runtime.service import run
        return run(args)
    if args.command == "replay":
        from .simulation.replay import run
        try:
            result=run(args.config,args.registry,args.input,args.output)
        except (OSError,ValueError) as exc:
            parser.error(str(exc))
        print(json.dumps(result["counts"]))
        return 0
    if args.command == "status":
        if args.state:
            import sqlite3
            with sqlite3.connect("file:"+str(args.state.resolve())+"?mode=ro",uri=True) as c:
                c.row_factory=sqlite3.Row
                print(json.dumps({"instances":[dict(r) for r in c.execute("SELECT id,cursor,status,halt FROM instances")],"orders":[dict(r) for r in c.execute("SELECT id,instance,status FROM commands")],"positions":[json.loads(r["body"]) for r in c.execute("SELECT body FROM positions")],"active_risk":[dict(r) for r in c.execute("SELECT * FROM reservations WHERE status!='RELEASED'")],"rejections":[json.loads(r["body"]) for r in c.execute("SELECT body FROM checkpoints WHERE id LIKE 'rejection:%'")]}))
        else:
            print(json.dumps({"stage":"paper-runtime","real_broker_enabled":False}))
        return 0
    if args.command == "validate-instance":
        from .contracts.config import Instance
        try:
            item = Instance.model_validate_json(args.path.read_text())
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
        print(json.dumps({"valid": True, "config_hash": item.hash, "mode": item.mode, "paper_runtime_available": True, "note": "Mandate validation only; registry and deployment readiness checked at startup."}))
        return 0
    try:
        result = validate_config(json.loads(args.path.read_text()))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))
    return 0
