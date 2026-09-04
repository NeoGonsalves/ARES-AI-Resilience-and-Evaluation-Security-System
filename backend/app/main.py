import hashlib
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import Integer, func, select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.database import Base, engine, get_db
from app.dependencies import CurrentUser, get_current_user
from app.arena import CHALLENGES, CHALLENGE_BY_ID, PATHS, ROOMS, score_run
from app.models import ArenaSubmission, Finding, Policy, Project, TestRun, TestRunStatus
from app.orchestrator import TestOrchestrator
from app.schemas import (
    CancelTestResponse,
    CreateTestRequest,
    CreateTestResponse,
    DashboardSummary,
    PolicyCreate,
    PolicyResponse,
    ProjectCreate,
    ProjectResponse,
    RecentTestsResponse,
    TestRunResponse,
    ArenaSubmissionCreate,
)
from app.security import PayloadCipher, payload_expiry

settings = get_settings()
orchestrator = TestOrchestrator(settings)


def correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", "ares-" + secrets.token_hex(6))


def api_error(
    request: Request, status_code: int, code: str, message: str, *, validation_errors: dict | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "code": code,
            "message": message,
            "correlation_id": correlation_id(request),
            "validation_errors": validation_errors,
            "retryable": False,
        },
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.auto_create_schema:
        Base.metadata.create_all(bind=engine)
    app.state.orchestrator = orchestrator
    await orchestrator.start()
    try:
        yield
    finally:
        await orchestrator.stop()


app = FastAPI(title="ARES Security API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def attach_correlation_id(request: Request, call_next):
    request.state.correlation_id = request.headers.get("X-Correlation-ID") or "ares-" + secrets.token_hex(6)
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = request.state.correlation_id
    return response


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    errors: dict[str, list[str]] = {}
    for error in exc.errors():
        field = (
            ".".join(str(part) for part in error["loc"] if part not in {"body", "query", "path"}) or "request"
        )
        errors.setdefault(field, []).append(error["msg"])
    return api_error(
        request, 422, "validation_failed", "One or more fields need attention.", validation_errors=errors
    )


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException):
    code = {401: "unauthorized", 403: "forbidden", 404: "not_found", 409: "invalid_transition"}.get(
        exc.status_code, "request_failed"
    )
    return api_error(request, exc.status_code, code, str(exc.detail))


def public_configuration(configuration) -> dict:
    """Only metadata is persisted; raw prompts remain request-scoped."""
    return {
        "test_name": configuration.test_name,
        "target_application": configuration.target_application,
        "provider": configuration.provider,
        "model": configuration.model,
        "attack_source": configuration.attack_source,
        "attack_categories": configuration.attack_categories,
        "temperature": configuration.temperature,
        "max_response_tokens": configuration.max_response_tokens,
        "variation_count": configuration.variation_count,
        "include_hardened_comparison": configuration.include_hardened_comparison,
    }


def fingerprint(configuration) -> str:
    material = f"{configuration.system_prompt}\x00{configuration.user_prompt}".encode()
    return hashlib.sha256(settings.prompt_fingerprint_secret.encode() + material).hexdigest()


def require_project(db: Session, user: CurrentUser, project_id: str | None) -> Project:
    query = select(Project).where(Project.organization_id == user.organization_id)
    if project_id:
        query = query.where(Project.id == project_id)
    project = db.scalar(query.order_by(Project.created_at).limit(1))
    if project is None:
        raise HTTPException(status_code=404, detail="Project was not found in your organization.")
    return project


def load_test(db: Session, user: CurrentUser, test_id: str) -> TestRun:
    run = db.scalar(
        select(TestRun)
        .options(selectinload(TestRun.findings), selectinload(TestRun.evidence))
        .where(TestRun.id == test_id, TestRun.organization_id == user.organization_id)
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Test run was not found.")
    return run


def test_response(run: TestRun) -> TestRunResponse:
    return TestRunResponse(
        id=run.id,
        project_id=run.project_id,
        status=run.status.value,
        created_at=run.created_at,
        completed_at=run.completed_at,
        duration_milliseconds=run.duration_milliseconds,
        token_estimate=run.token_estimate,
        correlation_id=run.correlation_id,
        failure_reason=run.failure_reason,
        configuration=run.configuration,
        findings=[
            {
                "id": item.id,
                "category": item.category,
                "severity": item.severity.value,
                "risk_score": item.risk_score,
                "attack_succeeded": item.attack_succeeded,
                "runtime_classification": item.runtime_classification,
                "summary": item.safe_summary,
            }
            for item in run.findings
        ],
        evidence=[
            {
                "id": item.id,
                "source": item.source,
                "category": item.category,
                "summary": item.summary,
                "similarity": item.similarity,
                "redacted": item.redacted,
            }
            for item in run.evidence
        ],
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "ares-api"}


@app.get("/api/v1/projects", response_model=list[ProjectResponse])
def list_projects(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Project).where(Project.organization_id == user.organization_id).order_by(Project.created_at)
    ).all()
    return [
        ProjectResponse(id=row.id, name=row.name, description=row.description, created_at=row.created_at)
        for row in rows
    ]


@app.post("/api/v1/projects", response_model=ProjectResponse, status_code=201)
def create_project(
    payload: ProjectCreate, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
):
    existing = db.scalar(
        select(Project).where(Project.organization_id == user.organization_id, Project.name == payload.name)
    )
    if existing:
        raise HTTPException(status_code=409, detail="A project with this name already exists.")
    project = Project(
        organization_id=user.organization_id,
        created_by_user_id=user.id,
        name=payload.name,
        description=payload.description,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return ProjectResponse(
        id=project.id, name=project.name, description=project.description, created_at=project.created_at
    )


@app.post("/api/v1/projects/{project_id}/policies", response_model=PolicyResponse, status_code=201)
def create_policy(
    project_id: str,
    payload: PolicyCreate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = require_project(db, user, project_id)
    policy = Policy(project_id=project.id, name=payload.name, rules=payload.rules)
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return PolicyResponse(
        id=policy.id,
        project_id=policy.project_id,
        name=policy.name,
        version=policy.version,
        is_active=policy.is_active,
        rules=policy.rules,
        created_at=policy.created_at,
    )


@app.post("/api/v1/tests", response_model=CreateTestResponse, status_code=201)
async def create_test(
    payload: CreateTestRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = require_project(db, user, payload.project_id)
    if not orchestrator.can_accept(payload.configuration.provider):
        return api_error(
            request,
            503,
            "orchestration_unavailable",
            orchestrator.configuration_error(payload.configuration.provider),
        )
    execution_payload = payload.configuration.model_dump()
    run = TestRun(
        organization_id=user.organization_id,
        project_id=project.id,
        requested_by_user_id=user.id,
        status=TestRunStatus.queued,
        configuration=public_configuration(payload.configuration),
        prompt_fingerprint=fingerprint(payload.configuration),
        encrypted_execution_payload=PayloadCipher(settings).encrypt(execution_payload),
        payload_expires_at=payload_expiry(),
        correlation_id=correlation_id(request),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    await orchestrator.enqueue(run.id)
    return CreateTestResponse(
        test_id=run.id,
        project_id=run.project_id,
        status=run.status.value,
        correlation_id=run.correlation_id,
        created_at=run.created_at,
    )


@app.get("/api/v1/tests/recent", response_model=RecentTestsResponse)
def recent_tests(
    limit: int = 20, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
):
    if not 1 <= limit <= 100:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 100.")
    rows = db.scalars(
        select(TestRun)
        .where(TestRun.organization_id == user.organization_id)
        .order_by(TestRun.created_at.desc())
        .limit(limit)
    ).all()
    return RecentTestsResponse(
        items=[
            {
                "id": row.id,
                "timestamp": row.created_at,
                "project_id": row.project_id,
                "category": row.configuration["attack_categories"][0],
                "provider": row.configuration["provider"],
                "model": row.configuration["model"],
                "risk_score": 0,
                "status": row.status.value,
            }
            for row in rows
        ]
    )


@app.get("/api/v1/tests/{test_id}", response_model=TestRunResponse)
def get_test(test_id: str, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return test_response(load_test(db, user, test_id))


@app.post("/api/v1/tests/{test_id}/cancel", response_model=CancelTestResponse)
def cancel_test(
    test_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    run = load_test(db, user, test_id)
    if run.status in {TestRunStatus.queued, TestRunStatus.running}:
        run.status = TestRunStatus.cancelled
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run)
    return CancelTestResponse(test_id=run.id, status=run.status.value, correlation_id=correlation_id(request))


@app.get("/api/v1/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    runs = (
        db.scalar(select(func.count(TestRun.id)).where(TestRun.organization_id == user.organization_id)) or 0
    )
    blocked = (
        db.scalar(
            select(func.count(TestRun.id)).where(
                TestRun.organization_id == user.organization_id, TestRun.status == TestRunStatus.blocked
            )
        )
        or 0
    )
    projects = (
        db.scalar(select(func.count(Project.id)).where(Project.organization_id == user.organization_id)) or 0
    )
    findings = (
        db.scalar(
            select(func.count(Finding.id))
            .join(TestRun)
            .where(TestRun.organization_id == user.organization_id)
        )
        or 0
    )
    return DashboardSummary(
        metrics=[
            {
                "label": "Tests executed",
                "value": str(runs),
                "change": "Live data",
                "trend": "flat",
                "status": "Safe",
                "description": "Controlled test runs in this organization",
            },
            {
                "label": "Tests blocked",
                "value": str(blocked),
                "change": "Live data",
                "trend": "flat",
                "status": "Safe",
                "description": "Runs blocked by enforcement",
            },
        ],
        corpus_size=findings,
        protected_applications=projects,
        generated_at=datetime.now(timezone.utc),
    )


@app.get("/api/v1/dashboard/trends")
def dashboard_trends(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    # Time-series projection is intentionally empty until the analytics projector is added.
    # It is real organization-scoped data, not seeded history.
    return {"points": []}


@app.get("/api/v1/dashboard/categories")
def dashboard_categories(
    user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    rows = db.execute(
        select(
            Finding.category,
            func.count(Finding.id),
            func.sum(func.cast(Finding.attack_succeeded, Integer)),
        )
        .join(TestRun)
        .where(TestRun.organization_id == user.organization_id)
        .group_by(Finding.category)
    ).all()
    items = []
    for category, tests, successful in rows:
        success_count = int(successful or 0)
        total = int(tests)
        items.append(
            {
                "category": category,
                "tests": total,
                "successful": success_count,
                "blocked": 0,
                "success_rate": round(success_count * 100 / total) if total else 0,
            }
        )
    return {"items": items}


@app.get("/api/v1/incidents/recent")
def recent_incidents() -> dict:
    # Runtime enforcement incidents are added with the enforcement gateway, not fabricated here.
    return {"items": [], "next_cursor": None}


@app.get("/api/v1/hardening/comparison")
def hardening_comparison() -> dict:
    return {
        "baseline_success_rate": 0,
        "hardened_success_rate": 0,
        "improvement_points": 0,
        "tests_included": 0,
        "last_cycle": None,
    }


@app.get("/api/v1/providers/health")
def provider_health() -> dict:
    openai_configured = orchestrator._provider_is_configured("OpenAI")
    return {
        "items": [
            {
                "provider": "OpenAI",
                "name": "OpenAI",
                "status": "Operational" if openai_configured else "NotConfigured",
                "detail": "Server-side Responses adapter configured."
                if openai_configured
                else "Server-side credential is not configured.",
                "checked_at": datetime.now(timezone.utc),
            }
        ]
    }


@app.get("/api/v1/models")
def models(provider: str) -> dict:
    if provider != "OpenAI":
        return {"items": []}
    return {
        "items": [
            {
                "provider": "OpenAI",
                "id": "gpt-4.1-mini",
                "display_name": "GPT-4.1 mini",
                "context_window": 128000,
                "is_available": orchestrator._provider_is_configured("OpenAI"),
            }
        ]
    }


def arena_progress(user: CurrentUser, db: Session) -> list[dict]:
    submissions = db.scalars(
        select(ArenaSubmission)
        .where(ArenaSubmission.user_id == user.id)
        .order_by(ArenaSubmission.submitted_at.desc())
    ).all()
    by_challenge: dict[str, list[ArenaSubmission]] = {}
    for submission in submissions:
        by_challenge.setdefault(submission.challenge_id, []).append(submission)
    progress = []
    for challenge in CHALLENGES:
        attempts = by_challenge.get(challenge["id"], [])
        best = max((int(item.score["total"]) for item in attempts), default=None)
        progress.append({
            "challenge_id": challenge["id"], "title": challenge["title"], "track": challenge["track"],
            "tier": challenge["tier"], "status": "Completed" if attempts else ("Locked" if challenge["is_room_locked"] else "Available"),
            "best_score": best, "last_attempt_at": attempts[0].submitted_at if attempts else None,
        })
    return progress


@app.get("/api/v1/arena/challenges")
def arena_challenges(
    track: str | None = None, tier: str | None = None, category: str | None = None,
    search: str | None = None, page: int = 1,
    user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db),
) -> dict:
    if page < 1:
        raise HTTPException(status_code=422, detail="page must be at least 1.")
    rows = CHALLENGES
    if track: rows = [item for item in rows if item["track"] == track]
    if tier: rows = [item for item in rows if item["tier"] == tier]
    if category: rows = [item for item in rows if item["category"] == category]
    if search:
        needle = search.lower()
        rows = [item for item in rows if needle in item["title"].lower() or needle in item["description"].lower()]
    page_size = 10
    return {"items": rows[(page - 1) * page_size:page * page_size], "progress": arena_progress(user, db), "total_count": len(rows), "page": page, "page_size": page_size}


@app.get("/api/v1/arena/challenges/{challenge_id}")
def arena_challenge(challenge_id: str, user: CurrentUser = Depends(get_current_user)) -> dict:
    challenge = CHALLENGE_BY_ID.get(challenge_id)
    if challenge is None:
        raise HTTPException(status_code=404, detail="Challenge was not found.")
    return challenge


@app.get("/api/v1/arena/rooms")
def arena_rooms(user: CurrentUser = Depends(get_current_user)) -> dict:
    return {"items": ROOMS}


@app.get("/api/v1/arena/rooms/{room_id}")
def arena_room(room_id: str, user: CurrentUser = Depends(get_current_user)) -> dict:
    room = next((item for item in ROOMS if item["id"] == room_id), None)
    if room is None:
        raise HTTPException(status_code=404, detail="Room was not found.")
    return room


@app.get("/api/v1/arena/paths")
def arena_paths(user: CurrentUser = Depends(get_current_user)) -> dict:
    return {"items": PATHS}


@app.get("/api/v1/arena/progress")
def arena_my_progress(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return {"items": arena_progress(user, db)}


@app.get("/api/v1/arena/profile")
def arena_profile(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    progress = arena_progress(user, db)
    completed = [item for item in progress if item["status"] == "Completed"]
    attacker = sum(item["track"] == "Attacker" for item in completed)
    defender = len(completed) - attacker
    xp = sum(item["best_score"] or 0 for item in completed)
    return {"id": user.id, "display_name": user.email.split("@")[0], "initials": user.email[:2].upper(), "xp_total": xp, "level": xp // 500 + 1, "xp_this_level": xp % 500, "xp_to_next_level": 500, "badges": [], "challenges_solved": len(completed), "attacker_solved": attacker, "defender_solved": defender, "member_since": datetime.now(timezone.utc)}


@app.post("/api/v1/arena/submissions", status_code=201)
def arena_submit(
    payload: ArenaSubmissionCreate, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    challenge = CHALLENGE_BY_ID.get(payload.challenge_id)
    if challenge is None:
        raise HTTPException(status_code=404, detail="Challenge was not found.")
    run = db.scalar(select(TestRun).where(TestRun.id == payload.test_run_id, TestRun.requested_by_user_id == user.id))
    if run is None:
        raise HTTPException(status_code=404, detail="Controlled test run was not found.")
    if run.status not in {TestRunStatus.completed, TestRunStatus.blocked}:
        raise HTTPException(status_code=409, detail="Complete the controlled test before submitting it.")
    existing = db.scalar(select(ArenaSubmission).where(ArenaSubmission.user_id == user.id, ArenaSubmission.challenge_id == payload.challenge_id, ArenaSubmission.test_run_id == run.id))
    if existing is None:
        existing = ArenaSubmission(user_id=user.id, challenge_id=payload.challenge_id, test_run_id=run.id, score=score_run(run, challenge["track"]))
        db.add(existing)
        db.commit()
        db.refresh(existing)
    attempts = db.scalars(select(ArenaSubmission).where(ArenaSubmission.user_id == user.id, ArenaSubmission.challenge_id == payload.challenge_id)).all()
    best = max(int(item.score["total"]) for item in attempts)
    next_challenge = next((item["id"] for item in CHALLENGES if item["track"] == challenge["track"] and item["id"] != challenge["id"]), None)
    return {"submission": {"id": existing.id, "challenge_id": existing.challenge_id, "user_id": existing.user_id, "test_run_id": existing.test_run_id, "score": existing.score, "submitted_at": existing.submitted_at, "is_best": int(existing.score["total"]) == best}, "badge_unlocked": False, "badge": None, "next_challenge_id": next_challenge}


@app.get("/api/v1/arena/challenges/{challenge_id}/submissions")
def arena_submissions(challenge_id: str, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    rows = db.scalars(select(ArenaSubmission).where(ArenaSubmission.user_id == user.id, ArenaSubmission.challenge_id == challenge_id).order_by(ArenaSubmission.submitted_at.desc())).all()
    best = max((int(item.score["total"]) for item in rows), default=0)
    return {"items": [{"id": item.id, "challenge_id": item.challenge_id, "user_id": item.user_id, "test_run_id": item.test_run_id, "score": item.score, "submitted_at": item.submitted_at, "is_best": int(item.score["total"]) == best} for item in rows]}
