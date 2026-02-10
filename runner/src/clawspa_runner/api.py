from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from .service import RunnerService


class ProofArtifact(BaseModel):
    ref: str
    summary: str | None = None


class ProofRequest(BaseModel):
    quest_id: str
    tier: str
    artifacts: list[ProofArtifact] = Field(default_factory=list)
    mode: str = "agent"


class GrantRequest(BaseModel):
    capabilities: list[str] = Field(default_factory=list)
    ttl_seconds: int = 3600
    scope: str = "manual"
    confirmed: bool = False


class RevokeRequest(BaseModel):
    grant_id: str | None = None
    capability: str | None = None


def create_app(service: RunnerService) -> FastAPI:
    app = FastAPI(title="ClawSpa Runner API", version="0.1")

    @app.get("/v1/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "version": "0.1", "schema_versions": {"quest": "0.1", "profile": "0.1"}}

    @app.get("/v1/packs")
    def list_packs() -> list[dict[str, Any]]:
        return service.quests.list_packs()

    @app.post("/v1/packs/sync")
    def sync_packs() -> dict[str, str]:
        return {"status": "noop", "message": "v0.1 local packs only"}

    @app.get("/v1/packs/{pack_id}")
    def get_pack(pack_id: str) -> dict[str, Any]:
        pack = service.quests.get_pack(pack_id)
        if not pack:
            raise HTTPException(status_code=404, detail="Pack not found")
        return pack

    @app.get("/v1/quests/{quest_id}")
    def get_quest(quest_id: str) -> dict[str, Any]:
        try:
            return service.get_quest(quest_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

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

    @app.get("/v1/profiles/human")
    def get_human_profile() -> dict[str, Any]:
        return service.get_profile("human")

    @app.put("/v1/profiles/human")
    def put_human_profile(profile: dict[str, Any]) -> dict[str, Any]:
        try:
            return service.put_profile("human", profile)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/v1/profiles/agent")
    def get_agent_profile() -> dict[str, Any]:
        return service.get_profile("agent")

    @app.put("/v1/profiles/agent")
    def put_agent_profile(profile: dict[str, Any]) -> dict[str, Any]:
        try:
            return service.put_profile("agent", profile)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/v1/profiles/alignment_snapshot")
    def get_alignment_snapshot() -> dict[str, Any]:
        return service.get_profile("alignment_snapshot")

    @app.post("/v1/profiles/alignment_snapshot/generate")
    def generate_alignment_snapshot() -> dict[str, Any]:
        return service.generate_alignment_snapshot()

    @app.get("/v1/plans/daily")
    def get_daily_plan(date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$")) -> dict[str, Any]:
        try:
            target = date_from_str(date)
            return service.get_daily_plan(target)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/plans/daily/generate")
    def generate_daily_plan(date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$")) -> dict[str, Any]:
        try:
            target = date_from_str(date)
            return service.generate_daily_plan(target)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/proofs")
    def submit_proof(request: ProofRequest) -> dict[str, Any]:
        artifact_ref = request.artifacts[0].ref if request.artifacts else ""
        try:
            return service.complete_quest(request.quest_id, request.tier, artifact_ref, actor_mode=request.mode)
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
    def grant_capabilities(request: GrantRequest) -> dict[str, Any]:
        try:
            return service.grant_capabilities(
                capabilities=request.capabilities,
                ttl_seconds=request.ttl_seconds,
                scope=request.scope,
                confirmed=request.confirmed,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/capabilities/revoke")
    def revoke_capabilities(request: RevokeRequest) -> dict[str, Any]:
        try:
            return service.revoke_capability(grant_id=request.grant_id, capability=request.capability)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app


def date_from_str(value: str) -> date:
    return date.fromisoformat(value)
