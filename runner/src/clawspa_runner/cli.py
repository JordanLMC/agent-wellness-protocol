from __future__ import annotations

import argparse
import json
import os
from datetime import date
from pathlib import Path
from uuid import uuid4

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
    default_actor_id = os.environ.get("CLAWSPA_ACTOR_ID", "unknown")

    plan_cmd = sub.add_parser("plan", help="Generate or read daily plan")
    plan_cmd.add_argument("--date", default=date.today().isoformat(), help="Date in YYYY-MM-DD")
    plan_cmd.add_argument("--actor-id", default=default_actor_id, help="Telemetry actor identifier")
    plan_cmd.add_argument("--weekly", action="store_true", help="Use weekly plan endpoint for the containing week")

    complete_cmd = sub.add_parser("complete", help="Record quest completion")
    complete_cmd.add_argument("--quest", required=True, help="Canonical quest ID")
    complete_cmd.add_argument("--tier", required=True, choices=["P0", "P1", "P2", "P3"])
    complete_cmd.add_argument("--artifact", required=True, help="Artifact path or summary reference")
    complete_cmd.add_argument("--actor", default="human", choices=["human", "agent", "system"])
    complete_cmd.add_argument("--actor-id", default=default_actor_id, help="Telemetry actor identifier")

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
    cap_grant.add_argument("--actor-id", default=default_actor_id, help="Telemetry actor identifier")
    cap_revoke = cap_sub.add_parser("revoke")
    cap_revoke.add_argument("--grant-id")
    cap_revoke.add_argument("--capability")
    cap_revoke.add_argument("--actor-id", default=default_actor_id, help="Telemetry actor identifier")

    proofs_cmd = sub.add_parser("proofs", help="Proof storage operations")
    proofs_sub = proofs_cmd.add_subparsers(dest="proofs_command", required=True)
    proofs_purge = proofs_sub.add_parser("purge", help="Purge stored proofs older than a range")
    proofs_purge.add_argument("--older-than", default=None, help="Range like 90d or 720h")
    proofs_purge.add_argument("--actor-id", default=default_actor_id, help="Telemetry actor identifier")

    telemetry_cmd = sub.add_parser("telemetry", help="Telemetry operations")
    telemetry_sub = telemetry_cmd.add_subparsers(dest="telemetry_command", required=True)
    telemetry_status = telemetry_sub.add_parser("status", help="Show telemetry status")
    telemetry_status.set_defaults(_telemetry_action="status")
    telemetry_verify = telemetry_sub.add_parser("verify", help="Verify telemetry hash-chain integrity")
    telemetry_verify.set_defaults(_telemetry_action="verify")
    telemetry_purge = telemetry_sub.add_parser("purge", help="Purge local telemetry events older than a range")
    telemetry_purge.add_argument("--older-than", default=None, help="Range like 30d or 720h")
    telemetry_purge.add_argument("--actor-id", default=default_actor_id, help="Telemetry actor identifier")
    telemetry_purge.set_defaults(_telemetry_action="purge")
    telemetry_export = telemetry_sub.add_parser("export", help="Export aggregated telemetry summary")
    telemetry_export.add_argument("--range", default="7d", help="Range window like 7d or 24h")
    telemetry_export.add_argument("--out", required=True, help="Output JSON path")
    telemetry_export.add_argument("--actor-id", default=None, help="Optional actor id filter")
    telemetry_snapshot = telemetry_sub.add_parser("snapshot", help="Create aggregated telemetry baseline snapshot")
    telemetry_snapshot.add_argument("--range", default="7d", help="Range window like 7d or 24h")
    telemetry_snapshot.add_argument("--out", default=None, help="Optional snapshot output path")
    telemetry_snapshot.add_argument("--actor-id", default=None, help="Optional actor id filter")
    telemetry_diff = telemetry_sub.add_parser("diff", help="Diff two telemetry baseline/export JSON files")
    telemetry_diff.add_argument("--a", required=True, help="Path to baseline/export JSON A")
    telemetry_diff.add_argument("--b", required=True, help="Path to baseline/export JSON B")
    telemetry_diff.add_argument("--out", default=None, help="Optional output path for JSON diff")
    telemetry_diff.add_argument("--format", choices=["text", "json"], default="text", help="Console output format")

    args = parser.parse_args()
    service = _service()
    trace_id = f"cli:{uuid4()}"

    if args.command == "plan":
        if args.weekly:
            plan = service.get_weekly_plan(
                date.fromisoformat(args.date),
                source="cli",
                actor="human",
                actor_id=args.actor_id,
                trace_id=trace_id,
            )
        else:
            plan = service.get_daily_plan(
                date.fromisoformat(args.date),
                source="cli",
                actor="human",
                actor_id=args.actor_id,
                trace_id=trace_id,
            )
        _print_plan(plan)
        return 0

    if args.command == "complete":
        result = service.complete_quest(
            args.quest,
            args.tier,
            args.artifact,
            actor_mode=args.actor,
            source="cli",
            actor_id=args.actor_id,
            trace_id=trace_id,
        )
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
                source="cli",
                actor="human",
                actor_id=args.actor_id,
                trace_id=trace_id,
            )
            print(json.dumps(result, indent=2))
            return 0
        if args.cap_command == "revoke":
            result = service.revoke_capability(
                grant_id=args.grant_id,
                capability=args.capability,
                source="cli",
                actor="human",
                actor_id=args.actor_id,
                trace_id=trace_id,
            )
            print(json.dumps(result, indent=2))
            return 0

    if args.command == "proofs":
        if args.proofs_command == "purge":
            result = service.proofs_purge(
                older_than=args.older_than,
                source="cli",
                actor="human",
                actor_id=args.actor_id,
                trace_id=trace_id,
            )
            print(json.dumps(result, indent=2))
            return 0

    if args.command == "telemetry":
        if args.telemetry_command == "status":
            print(json.dumps(service.telemetry_status(), indent=2))
            return 0
        if args.telemetry_command == "verify":
            result = service.telemetry_verify()
            print(json.dumps(result, indent=2))
            return 0 if result.get("ok") else 1
        if args.telemetry_command == "purge":
            print(
                json.dumps(
                    service.telemetry_purge(
                        older_than=args.older_than,
                        source="cli",
                        actor="human",
                        actor_id=args.actor_id,
                        trace_id=trace_id,
                    ),
                    indent=2,
                )
            )
            return 0
        if args.telemetry_command == "export":
            summary = service.telemetry_export(args.range, Path(args.out), actor_id=args.actor_id)
            print(json.dumps(summary, indent=2))
            return 0
        if args.telemetry_command == "snapshot":
            snapshot = service.telemetry_snapshot(
                args.range,
                actor_id=args.actor_id,
                out_path=Path(args.out) if args.out else None,
            )
            print(
                json.dumps(
                    {
                        "path": snapshot["path"],
                        "sha256": snapshot["sha256"],
                    },
                    indent=2,
                )
            )
            return 0
        if args.telemetry_command == "diff":
            diff = service.telemetry_diff(
                Path(args.a),
                Path(args.b),
                out_path=Path(args.out) if args.out else None,
            )
            if args.format == "json":
                print(json.dumps(diff["diff"], indent=2))
            else:
                print(diff["text"])
                if args.out:
                    print(f"JSON diff written to {args.out}")
            return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
