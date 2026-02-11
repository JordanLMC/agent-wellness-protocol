from __future__ import annotations

"""HTTP API surface for local-first runner operations."""

from datetime import date
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, Field

from .service import RunnerService
from .telemetry import sanitize_actor_id


class ProofArtifact(BaseModel):
    """One redacted proof reference submitted for quest completion."""

    ref: str = Field(min_length=1, max_length=512)
    summary: str | None = Field(default=None, max_length=280)


class ProofRequest(BaseModel):
    """Payload for `/v1/proofs` with optional actor identity override."""

    quest_id: str
    tier: str
    artifacts: list[ProofArtifact] = Field(default_factory=list)
    mode: str = "agent"
    actor_id: str | None = Field(default=None, max_length=200)


class GrantRequest(BaseModel):
    """Capability grant request gated by a human-issued ticket token."""

    capabilities: list[str] = Field(default_factory=list)
    ttl_seconds: int = 3600
    scope: str = "manual"
    ticket_token: str = Field(min_length=1)
    confirm: bool = False
    actor_id: str | None = Field(default=None, max_length=200)


class RevokeRequest(BaseModel):
    """Capability revoke request scoped by grant id or capability name."""

    grant_id: str | None = None
    capability: str | None = None
    actor_id: str | None = Field(default=None, max_length=200)


def create_app(service: RunnerService) -> FastAPI:
    """Create API routes backed by `RunnerService` with actor/source attribution."""

    app = FastAPI(title="ClawSpa Runner API", version="0.1")

    @app.middleware("http")
    async def trace_id_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        incoming = (request.headers.get("x-clawspa-trace-id") or "").strip()
        trace_id = sanitize_actor_id(incoming) if incoming else f"api:{uuid4()}"
        if not trace_id or trace_id == "unknown":
            trace_id = f"api:{uuid4()}"
        request.state.trace_id = trace_id
        response = await call_next(request)
        response.headers["X-Clawspa-Trace-Id"] = trace_id
        return response

    def request_context(
        request: Request,
        default_actor: str = "human",
        body_actor_id: str | None = None,
    ) -> tuple[str, str, str]:
        """Resolve normalized `(source, actor_kind, actor_id)` with header precedence."""

        source = request.headers.get("x-clawspa-source", "api").strip().lower()
        actor = request.headers.get("x-clawspa-actor", default_actor).strip().lower()
        header_actor_id = (request.headers.get("x-clawspa-actor-id") or "").strip()
        body_actor_id_value = (body_actor_id or "").strip()
        if source not in {"cli", "api", "mcp"}:
            source = "api"
        if actor not in {"human", "agent", "system"}:
            actor = default_actor
        actor_id = header_actor_id or body_actor_id_value or f"{source}:unknown"
        return source, actor, actor_id

    def request_trace_id(request: Request) -> str:
        value = getattr(request.state, "trace_id", None)
        if isinstance(value, str) and value:
            return value
        return f"api:{uuid4()}"

    @app.get("/v1/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "version": "0.1", "schema_versions": {"quest": "0.1", "profile": "0.1"}}

    @app.get("/v1/packs")
    def list_packs() -> list[dict[str, Any]]:
        return service.quests.list_packs()

    @app.post("/v1/packs/sync")
    def sync_packs() -> dict[str, Any]:
        return service.sync_packs()

    @app.get("/v1/packs/{pack_id}")
    def get_pack(pack_id: str) -> dict[str, Any]:
        pack = service.quests.get_pack(pack_id)
        if not pack:
            raise HTTPException(status_code=404, detail="Pack not found")
        return pack

    @app.get("/v1/quests/search")
    def search_quests(
        pillar: str | None = None,
        tag: str | None = None,
        risk_level: str | None = None,
        mode: str | None = None,
    ) -> list[dict[str, Any]]:
        try:
            return service.search_quests(pillar=pillar, tag=tag, risk_level=risk_level, mode=mode)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/v1/quests/{quest_id}")
    def get_quest(quest_id: str) -> dict[str, Any]:
        try:
            return service.get_quest(quest_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/v1/profiles/human")
    def get_human_profile() -> dict[str, Any]:
        return service.get_profile("human")

    @app.put("/v1/profiles/human")
    def put_human_profile(profile: dict[str, Any], request: Request) -> dict[str, Any]:
        try:
            source, actor, actor_id = request_context(request, default_actor="human")
            return service.put_profile(
                "human",
                profile,
                source=source,
                actor=actor,
                actor_id=actor_id,
                trace_id=request_trace_id(request),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/v1/profiles/agent")
    def get_agent_profile() -> dict[str, Any]:
        return service.get_profile("agent")

    @app.put("/v1/profiles/agent")
    def put_agent_profile(profile: dict[str, Any], request: Request) -> dict[str, Any]:
        try:
            source, actor, actor_id = request_context(request, default_actor="agent")
            return service.put_profile(
                "agent",
                profile,
                source=source,
                actor=actor,
                actor_id=actor_id,
                trace_id=request_trace_id(request),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/v1/profiles/alignment_snapshot")
    def get_alignment_snapshot() -> dict[str, Any]:
        return service.get_profile("alignment_snapshot")

    @app.post("/v1/profiles/alignment_snapshot/generate")
    def generate_alignment_snapshot() -> dict[str, Any]:
        return service.generate_alignment_snapshot()

    @app.get("/v1/plans/daily")
    def get_daily_plan(
        request: Request,
        date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    ) -> dict[str, Any]:
        try:
            target = date_from_str(date)
            source, actor, actor_id = request_context(request, default_actor="human")
            return service.get_daily_plan(
                target,
                source=source,
                actor=actor,
                actor_id=actor_id,
                trace_id=request_trace_id(request),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/plans/daily/generate")
    def generate_daily_plan(
        request: Request,
        date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    ) -> dict[str, Any]:
        try:
            target = date_from_str(date)
            source, actor, actor_id = request_context(request, default_actor="human")
            return service.generate_daily_plan(
                target,
                source=source,
                actor=actor,
                actor_id=actor_id,
                trace_id=request_trace_id(request),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/v1/plans/weekly")
    def get_weekly_plan(
        request: Request,
        date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    ) -> dict[str, Any]:
        try:
            target = date_from_str(date)
            source, actor, actor_id = request_context(request, default_actor="human")
            return service.get_weekly_plan(
                target,
                source=source,
                actor=actor,
                actor_id=actor_id,
                trace_id=request_trace_id(request),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/plans/weekly/generate")
    def generate_weekly_plan(
        request: Request,
        date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    ) -> dict[str, Any]:
        try:
            target = date_from_str(date)
            source, actor, actor_id = request_context(request, default_actor="human")
            return service.generate_weekly_plan(
                target,
                source=source,
                actor=actor,
                actor_id=actor_id,
                trace_id=request_trace_id(request),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/proofs")
    def submit_proof(request: ProofRequest, http_request: Request) -> dict[str, Any]:
        artifact_refs = [item.ref for item in request.artifacts]
        primary_artifact = artifact_refs[0] if artifact_refs else ""
        try:
            source, actor_kind, actor_id = request_context(
                http_request,
                default_actor=request.mode if request.mode in {"human", "agent"} else "agent",
                body_actor_id=request.actor_id,
            )
            return service.complete_quest(
                request.quest_id,
                request.tier,
                primary_artifact,
                actor_mode=actor_kind,
                artifacts=artifact_refs[1:],
                source=source,
                actor_id=actor_id,
                trace_id=request_trace_id(http_request),
            )
        except (ValueError, PermissionError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/v1/proofs")
    def list_proofs(quest_id: str | None = None, date_range: str | None = None) -> list[dict[str, Any]]:
        try:
            return service.list_proofs(quest_id=quest_id, date_range=date_range)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/v1/scorecard")
    def get_scorecard() -> dict[str, Any]:
        return service.get_scorecard()

    @app.get("/v1/scorecard/export")
    def export_scorecard() -> dict[str, Any]:
        out = service.home / "state" / "scorecard.export.json"
        return service.export_scorecard(out)

    @app.get("/v1/capabilities")
    def get_capabilities() -> dict[str, Any]:
        return service.get_capabilities()

    @app.post("/v1/capabilities/grant")
    def grant_capabilities(request: GrantRequest, http_request: Request) -> dict[str, Any]:
        header_confirm = (http_request.headers.get("x-clawspa-confirm") or "").strip().lower() == "true"
        if not (request.confirm and header_confirm):
            raise HTTPException(
                status_code=400,
                detail="Capability grant requires body confirm=true and header X-Clawspa-Confirm: true.",
            )
        try:
            source, actor, actor_id = request_context(http_request, default_actor="human", body_actor_id=request.actor_id)
            return service.grant_capabilities_with_ticket(
                capabilities=request.capabilities,
                ttl_seconds=request.ttl_seconds,
                scope=request.scope,
                ticket_token=request.ticket_token,
                source=source,
                actor=actor,
                actor_id=actor_id,
                trace_id=request_trace_id(http_request),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/capabilities/revoke")
    def revoke_capabilities(request: RevokeRequest, http_request: Request) -> dict[str, Any]:
        try:
            source, actor, actor_id = request_context(http_request, default_actor="human", body_actor_id=request.actor_id)
            return service.revoke_capability(
                grant_id=request.grant_id,
                capability=request.capability,
                source=source,
                actor=actor,
                actor_id=actor_id,
                trace_id=request_trace_id(http_request),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app


def date_from_str(value: str) -> date:
    """Parse `YYYY-MM-DD` into a date object."""

    return date.fromisoformat(value)
