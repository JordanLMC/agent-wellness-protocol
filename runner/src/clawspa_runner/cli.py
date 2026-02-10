from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import uvicorn

from .api import create_app
from .paths import discover_repo_root
from .service import RunnerService


def _service() -> RunnerService:
    repo_root = discover_repo_root()
    return RunnerService.create(repo_root)


def _print_plan(plan: dict) -> None:
    print(f"Date: {plan['date']}")
    for quest in plan.get("quests", []):
        q = quest.get("quest", {})
        print(f"- {q.get('id')} :: {q.get('title')}")
        steps = q.get("steps", {})
        human_steps = steps.get("human", [])
        agent_steps = steps.get("agent", [])
        if human_steps:
            print("  human:")
            for idx, step in enumerate(human_steps, start=1):
                print(f"    {idx}. [{step.get('type')}] {json.dumps(step, ensure_ascii=True)}")
        if agent_steps:
            print("  agent:")
            for idx, step in enumerate(agent_steps, start=1):
                print(f"    {idx}. [{step.get('type')}] {json.dumps(step, ensure_ascii=True)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="ClawSpa runner CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    plan_cmd = sub.add_parser("plan", help="Generate or read daily plan")
    plan_cmd.add_argument("--date", default=date.today().isoformat(), help="Date in YYYY-MM-DD")

    complete_cmd = sub.add_parser("complete", help="Record quest completion")
    complete_cmd.add_argument("--quest", required=True, help="Canonical quest ID")
    complete_cmd.add_argument("--tier", required=True, choices=["P0", "P1", "P2", "P3"])
    complete_cmd.add_argument("--artifact", required=True, help="Artifact path or summary reference")

    sub.add_parser("scorecard", help="Print current scorecard")

    export_cmd = sub.add_parser("export-scorecard", help="Export scorecard to file")
    export_cmd.add_argument("--out", required=True, help="Output JSON path")

    profile_cmd = sub.add_parser("profile", help="Profile operations")
    profile_sub = profile_cmd.add_subparsers(dest="profile_command", required=True)
    profile_sub.add_parser("init", help="Initialize local profile files")

    api_cmd = sub.add_parser("api", help="Run local API server")
    api_cmd.add_argument("--host", default="127.0.0.1")
    api_cmd.add_argument("--port", type=int, default=8000)

    cap_cmd = sub.add_parser("capability", help="Capability grants")
    cap_sub = cap_cmd.add_subparsers(dest="cap_command", required=True)
    cap_ticket = cap_sub.add_parser("ticket", help="Create human confirmation ticket for capability grant")
    cap_ticket.add_argument("--cap", action="append", required=True, help="Capability name (repeatable)")
    cap_ticket.add_argument("--ttl-seconds", type=int, default=900)
    cap_ticket.add_argument("--scope", default="manual")
    cap_ticket.add_argument("--reason", default="human approved temporary elevation")
    cap_grant = cap_sub.add_parser("grant")
    cap_grant.add_argument("--cap", action="append", required=True, help="Capability name (repeatable)")
    cap_grant.add_argument("--ttl-seconds", type=int, default=3600)
    cap_grant.add_argument("--scope", default="manual")
    cap_grant.add_argument("--ticket", required=True, help="Single-use grant ticket token")
    cap_revoke = cap_sub.add_parser("revoke")
    cap_revoke.add_argument("--grant-id")
    cap_revoke.add_argument("--capability")

    args = parser.parse_args()
    service = _service()

    if args.command == "plan":
        plan = service.get_daily_plan(date.fromisoformat(args.date))
        _print_plan(plan)
        return 0

    if args.command == "complete":
        result = service.complete_quest(args.quest, args.tier, args.artifact)
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "scorecard":
        print(json.dumps(service.get_scorecard(), indent=2))
        return 0

    if args.command == "export-scorecard":
        export = service.export_scorecard(Path(args.out))
        print(json.dumps(export, indent=2))
        return 0

    if args.command == "profile":
        if args.profile_command == "init":
            print(json.dumps(service.init_profiles(), indent=2))
            return 0

    if args.command == "api":
        app = create_app(service)
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
        return 0

    if args.command == "capability":
        if args.cap_command == "ticket":
            result = service.create_grant_ticket(
                capabilities=args.cap,
                ttl_seconds=args.ttl_seconds,
                scope=args.scope,
                reason=args.reason,
            )
            print(json.dumps(result, indent=2))
            return 0
        if args.cap_command == "grant":
            result = service.grant_capabilities_with_ticket(
                capabilities=args.cap,
                ttl_seconds=args.ttl_seconds,
                scope=args.scope,
                ticket_token=args.ticket,
            )
            print(json.dumps(result, indent=2))
            return 0
        if args.cap_command == "revoke":
            result = service.revoke_capability(grant_id=args.grant_id, capability=args.capability)
            print(json.dumps(result, indent=2))
            return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
