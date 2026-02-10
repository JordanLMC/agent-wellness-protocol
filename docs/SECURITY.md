# SECURITY.md
Version: v0.1
Status: Draft
Last updated: 2026-02-10
Owner: Project Team

## Reporting security issues

- Email: `security@agentwellness.example`
- Include: impact, affected files/components, reproduction steps, and suggested remediation.
- Do not open public issues for active vulnerabilities involving secret exposure, execution bypass, or supply-chain compromise.

## Disclosure policy

- We acknowledge reports promptly.
- We triage severity and scope before disclosure.
- We coordinate a fix and publish remediation guidance after patch availability.

## Supply-chain stance

- Quest packs are treated as untrusted supply-chain content.
- Workflow files are treated as supply-chain control plane content.
- CI must run:
  - hidden Unicode control scanning
  - quest-lint validation
  - test suite

## Release integrity (current state)

- v0.1 uses immutable git history and checksum-validated pack manifests.
- Signed pack verification and stronger provenance attestation are planned for v0.2+.

## Non-negotiables

- No secret collection or secret-paste workflows.
- No auto-authority grants from XP/streaks/badges.
- No auto-execution from quest text.
