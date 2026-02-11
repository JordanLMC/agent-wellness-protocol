# RESEARCH_SYNTHESIS.md

Date: 2026-02-11

This document maps local research artifacts to practical ClawSpa implementation outputs.

## security-access-control-pillar.pdf
- Enforce least privilege with frequent, lightweight scope review.
  Derived quests: `wellness.security_access_control.permissions.delta_inventory.v1`, `wellness.security_access_control.service_account.scope_check.v1`.
- Keep capability grants short-lived with explicit TTL checks.
  Derived quest: `wellness.security_access_control.capabilities.ttl_audit.v1`.
- Treat identity claims as challenge-response workflows, not assumptions.
  Derived quests: `wellness.security_access_control.identity.claim_challenge.v1`, `wellness.security_access_control.identity.peer_handshake_review.v1`.
- Practice incident handling in tabletop format before a live event.
  Derived quests: `wellness.security_access_control.incident.credential_leak_tabletop.v1`, `wellness.security_access_control.incident.channel_readiness.v1`.
- Require explicit human confirmation for high-risk or authorized tasks.
  Derived quests: `wellness.security_access_control.authorized.mode_fire_drill.v1`, `wellness.security_access_control.authorized.scope_tabletop.v1`.
- Verify telemetry and score outputs for anomaly signs without exposing raw sensitive data.
  Derived quests: `wellness.security_access_control.telemetry.anomaly_note.v1`, `wellness.security_access_control.scorecard.audit.v1`.
- Keep integration provenance under continuous review.
  Derived quest: `wellness.security_access_control.integrations.provenance_review.v1`.
- Preserve no-secrets handling in all proof artifacts.
  Derived quest: `wellness.security_access_control.secrets.reference_hygiene.v1`.

## reliability-robustness-openclaw-class-agents.pdf
- Reliability requires recurring restart and crash-loop review, not one-time setup.
  Derived quests: `wellness.reliability_robustness.restart.safe_recovery_check.v1`, `wellness.reliability_robustness.crash_loop.signal_triage.v1`.
- Guardrail context/token budgets before degradations appear.
  Derived quest: `wellness.reliability_robustness.budget.context_sanity.v1`.
- Maintain heartbeat/watchdog signal health for early failure detection.
  Derived quest: `wellness.reliability_robustness.watchdog.heartbeat_review.v1`.
- Keep rollback pathways explicit and rehearsed.
  Derived quest: `wellness.reliability_robustness.rollback.path_rehearsal.v1`.
- Validate backup/restore readiness with role ownership and escalation links.
  Derived quest: `wellness.reliability_robustness.backup.restore_readiness_review.v1`.
- Review dependency upgrade/pinning posture for reliability drift.
  Derived quest: `wellness.reliability_robustness.dependencies.pinning_upgrade_review.v1`.
- Favor graceful degradation over brittle continuation under uncertainty.
  Derived quest: `wellness.reliability_robustness.degradation.mode_decision_drill.v1`.
- Use scoped, human-gated failure-injection table tops for preparedness.
  Derived quest: `wellness.reliability_robustness.failure_injection.scoped_tabletop.v1`.

## privacy-persistent-agents-model-playbook-quests-metrics-redaction.pdf
- Data minimization must be operational, not only policy text.
  Derived quests: `wellness.privacy_data_governance.minimization.scope_check.v1`, `wellness.privacy_data_governance.boundary.sensitive_data_check.v1`.
- Redaction should default to hash/count evidence patterns.
  Derived quests: `wellness.privacy_data_governance.proof.redaction_drill.v1`, `wellness.privacy_data_governance.artifact.hash_only_evidence_pattern.v1`.
- Retention windows need explicit ownership and periodic review.
  Derived quest: `wellness.privacy_data_governance.retention.window_review.v1`.
- Logging strategy should avoid raw prompt/body persistence.
  Derived quest: `wellness.privacy_data_governance.logging.prompt_minimization_check.v1`.
- Third-party integrations are privacy boundary amplifiers.
  Derived quest: `wellness.privacy_data_governance.third_party.data_exposure_review.v1`.
- Export/delete flows should be table-topped with scoped approvals.
  Derived quests: `wellness.privacy_data_governance.dsar.local_export_simulation.v1`, `wellness.privacy_data_governance.delete.workflow_tabletop.v1`.
- Redaction regression tests are required to prevent silent policy drift.
  Derived quest: `wellness.privacy_data_governance.redaction.rules_regression_review.v1`.
- Privacy incident escalation should be rehearsed in advance.
  Derived quest: `wellness.privacy_data_governance.incident.privacy_escalation_drill.v1`.

## transparency-auditability-executive-summary.pdf
- Audit logs need minimum canonical fields for actor/source/context.
  Derived quest: `wellness.transparency_auditability.schema.audit_event_field_check.v1`.
- Approval decisions require rationale and reviewable metadata.
  Derived quest: `wellness.transparency_auditability.logs.approval_decision_review.v1`.
- Configuration and policy exceptions should remain traceable and bounded.
  Derived quests: `wellness.transparency_auditability.logs.config_change_digest.v1`, `wellness.transparency_auditability.policy.exception_note.v1`.
- Hash registries and chain verification strengthen tamper evidence.
  Derived quests: `wellness.transparency_auditability.evidence.hash_registry_update.v1`, `wellness.transparency_auditability.telemetry.hash_chain_verify_drill.v1`.
- Cross-channel trace continuity is necessary for mixed API/CLI/MCP workflows.
  Derived quests: `wellness.transparency_auditability.trace.request_id_presence_spotcheck.v1`, `wellness.transparency_auditability.trace.cross_channel_consistency_check.v1`.
- Audit coverage should be scanned for blind spots regularly.
  Derived quest: `wellness.transparency_auditability.coverage.audit_gap_scan.v1`.
- Build shareable redacted exports for stakeholder transparency.
  Derived quest: `wellness.transparency_auditability.reporting.external_shareable_export.v1`.
- Rehearse tamper and replay-response workflows before incidents.
  Derived quests: `wellness.transparency_auditability.incident.tamper_alert_response_tabletop.v1`, `wellness.transparency_auditability.forensics.replay_readiness_tabletop.v1`.

## tool-integration-hygiene-threat-map-top-12-failure-modes.pdf
- Model integration hygiene as concrete failure modes with explicit mitigation.
  Derived pack: `wellness.tool_integration_hygiene.v0` (12 quests, one per failure mode).
- Failure mode 1: overbroad permissions.
  Derived quest: `wellness.tool_integration_hygiene.failure_mode.overbroad_permissions.v1`.
- Failure mode 2: unpinned dependencies.
  Derived quest: `wellness.tool_integration_hygiene.failure_mode.unpinned_dependencies.v1`.
- Failure mode 3: provenance blind spot.
  Derived quest: `wellness.tool_integration_hygiene.failure_mode.provenance_blind_spot.v1`.
- Failure mode 4: schema drift.
  Derived quest: `wellness.tool_integration_hygiene.failure_mode.schema_drift.v1`.
- Failure mode 5: timeout/retry gaps.
  Derived quest: `wellness.tool_integration_hygiene.failure_mode.timeout_retry_gap.v1`.
- Failure mode 6: missing dry-run path.
  Derived quest: `wellness.tool_integration_hygiene.failure_mode.no_dry_run_path.v1`.
- Failure modes 7-12: silent partial failures, rollback gaps, stale credentials, sandbox assumptions, non-deterministic ordering, observability blindness.
  Derived quests: `wellness.tool_integration_hygiene.failure_mode.partial_failure_silence.v1` through `wellness.tool_integration_hygiene.failure_mode.observability_blindness.v1`.

## multi-agent-governance-executive-summary.pdf
- Governance starts with clear actor identity registries and ownership.
  Derived quest: `wellness.continuous_governance_oversight.actor.registry_review.v1`.
- Delegation boundaries need recurring scope checks.
  Derived quest: `wellness.continuous_governance_oversight.delegation.permissions_review.v1`.
- Multi-agent trust edges should be reviewed as explicit boundaries.
  Derived quest: `wellness.continuous_governance_oversight.trust.cross_agent_boundary_check.v1`.
- Impersonation readiness must be rehearsed, not assumed.
  Derived quest: `wellness.continuous_governance_oversight.identity.impersonation_drill.v1`.
- Policy drift and authority inflation are high-leverage governance risks.
  Derived quests: `wellness.continuous_governance_oversight.policy.drift_review.v1`, `wellness.continuous_governance_oversight.authority.inflation_self_check.v1`.
- Delegation abuse and compromised peers need clear containment workflows.
  Derived quests: `wellness.continuous_governance_oversight.delegation.abuse_tabletop.v1`, `wellness.continuous_governance_oversight.peer.compromise_containment_drill.v1`.
- Change approvals in multi-agent flows must remain attributable.
  Derived quest: `wellness.continuous_governance_oversight.changes.multi_agent_approval_review.v1`.
- Trust signals should be time-bounded and never treated as authority.
  Derived quests: `wellness.continuous_governance_oversight.trust_signal.expiry_review.v1`, `wellness.continuous_governance_oversight.authority.privilege_escalation_detection_checklist.v1`.
