# PACKS.md
Version: v0.1
Status: Draft
Last updated: 2026-02-11
Owner: Project Team

## Purpose

Provide a quick reference for available quest packs and intended use.

## Available Packs

| Pack ID | Focus | Typical users | Risk profile | Mode mix |
|---|---|---|---|---|
| `wellness.core.v0` | Baseline daily/weekly/monthly wellness routines | All operators and persistent agents | Low to high (gated) | Mostly safe; selected authorized/high-risk drills |
| `wellness.home_security.v0` | Home/local environment posture checks | Individual operators running local setups | Low to medium | Safe-first |
| `wellness.security_access_control.v0` | Access control, permissions, identity checks, credential tabletop drills | Operators managing integration and authorization boundaries | Medium to high | Safe + authorized (human-confirmed) |
| `wellness.reliability_robustness.v0` | Restart/rollback/readiness and resilience rehearsal | Teams prioritizing uptime and operational continuity | Low to high | Safe-first with scoped authorized drills |
| `wellness.privacy_data_governance.v0` | Retention, minimization, redaction, export/delete workflows | Teams handling sensitive metadata and persistent logs | Low to high | Safe-first with scoped authorized workflows |
| `wellness.transparency_auditability.v0` | Auditability, traceability, tamper-evident telemetry workflows | Teams needing explainable and reviewable operation trails | Low to high | Safe-first |
| `wellness.tool_integration_hygiene.v0` | Top-12 integration failure mode diagnostics and mitigations | Teams operating diverse tool/plugin ecosystems | Medium to high | Safe-first with scoped authorized checks |
| `wellness.continuous_governance_oversight.v0` | Multi-agent governance, delegation boundaries, authority calibration | Multi-agent operators and stewards | Medium to high | Safe + authorized governance table tops |

## Notes

- All packs are local-first and linted/checksummed supply-chain artifacts.
- Safe Mode is default.
- Authorized Mode quests require explicit capability grants and human confirmation.
- XP and streaks never grant authority.
