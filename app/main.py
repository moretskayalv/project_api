from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from .auth import create_access_token, get_current_user, hash_password, verify_password
from .cache import cache
from .database import get_session, init_db, engine
from .models import User, Link, Project, ExpiredLinkHistory
from .schemas import (
    CleanupConfigRequest,
    ExpiredLinkHistoryRead,
    LinkCreate,
    LinkResponse,
    LinkStatsResponse,
    LinkUpdate,
    LoginRequest,
    ProjectCreate,
    ProjectRead,
    RegisterRequest,
    SearchResponse,
    TokenResponse,
)
from .utils import cleanup_expired_links, cleanup_unused_links, set_unused_days_threshold, unique_short_code


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with Session(engine) as session:
        cleanup_expired_links(session)
        cleanup_unused_links(session)
    yield


app = FastAPI(title="URL Shortener API", version="1.0.0", lifespan=lifespan)


def build_short_url(request: Request, short_code: str) -> str:
    return str(request.base_url).rstrip("/") + f"/links/{short_code}"


def get_link_or_404(session: Session, short_code: str) -> Link:
    link = session.exec(select(Link).where(Link.short_code == short_code)).first()
    if not link:
        raise HTTPException(status_code=404, detail="Короткая ссылка не найдена")
    if link.expires_at and link.expires_at <= datetime.utcnow():
        session.delete(link)
        session.commit()
        raise HTTPException(status_code=404, detail="Ссылка истекла")
    return link


@app.post("/auth/register", response_model=TokenResponse, status_code=201)
def register(payload: RegisterRequest, session: Session = Depends(get_session)):
    existing = session.exec(
        select(User).where((User.username == payload.username) | (User.email == payload.email))
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Пользователь с таким username/email уже существует")

    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    session.add(user)
    session.commit()
    return TokenResponse(access_token=create_access_token(user.username))


@app.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.username == payload.username)).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Неверные учетные данные")
    return TokenResponse(access_token=create_access_token(user.username))


@app.post("/projects", response_model=ProjectRead, status_code=201)
def create_project(
    payload: ProjectCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    project = Project(name=payload.name, owner_id=current_user.id)
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


@app.get("/projects", response_model=list[ProjectRead])
def list_projects(
    session: Session = Depends(get_session), current_user: User = Depends(get_current_user)
):
    return session.exec(select(Project).where(Project.owner_id == current_user.id)).all()


@app.post("/links/shorten", response_model=LinkResponse, status_code=201)
def create_short_link(
    payload: LinkCreate,
    request: Request,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(lambda: None),
):
    cleanup_expired_links(session)

    owner_id = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            token = auth_header.split(" ", 1)[1]
            from .auth import jwt, SECRET_KEY, ALGORITHM
            username = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM]).get("sub")
            if username:
                user = session.exec(select(User).where(User.username == username)).first()
                if user:
                    owner_id = user.id
        except Exception:
            owner_id = None

    if payload.custom_alias:
        exists = session.exec(
            select(Link).where((Link.short_code == payload.custom_alias) | (Link.custom_alias == payload.custom_alias))
        ).first()
        if exists:
            raise HTTPException(status_code=400, detail="custom_alias уже занят")
        short_code = payload.custom_alias
    else:
        short_code = unique_short_code(session)

    if payload.project_id and not owner_id:
        raise HTTPException(status_code=401, detail="Проект можно указывать только авторизованному пользователю")

    if payload.project_id:
        project = session.get(Project, payload.project_id)
        if not project or project.owner_id != owner_id:
            raise HTTPException(status_code=404, detail="Проект не найден")

    link = Link(
        short_code=short_code,
        original_url=payload.original_url,
        custom_alias=payload.custom_alias,
        owner_id=owner_id,
        expires_at=payload.expires_at,
        project_id=payload.project_id,
    )
    session.add(link)
    session.commit()
    session.refresh(link)
    return LinkResponse(
        short_code=link.short_code,
        short_url=build_short_url(request, link.short_code),
        original_url=link.original_url,
        expires_at=link.expires_at,
        project_id=link.project_id,
    )


@app.get("/links/search", response_model=SearchResponse)
def search_by_original_url(original_url: str, session: Session = Depends(get_session)):
    cached = cache.get(f"search:{original_url}")
    if cached:
        return cached
    link = session.exec(select(Link).where(Link.original_url == original_url)).first()
    result = SearchResponse(
        found=bool(link),
        short_code=link.short_code if link else None,
        original_url=link.original_url if link else None,
    )
    cache.set(f"search:{original_url}", result, ttl_seconds=120)
    return result


@app.get("/links/{short_code}")
def redirect_to_original(short_code: str, session: Session = Depends(get_session)):
    cleanup_expired_links(session)
    link = get_link_or_404(session, short_code)
    link.clicks += 1
    link.last_used_at = datetime.utcnow()
    session.add(link)
    session.commit()
    cache.delete_prefix(f"stats:{short_code}")
    return RedirectResponse(url=link.original_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@app.get("/links/{short_code}/stats", response_model=LinkStatsResponse)
def link_stats(short_code: str, session: Session = Depends(get_session)):
    cached = cache.get(f"stats:{short_code}")
    if cached:
        return cached
    cleanup_expired_links(session)
    link = get_link_or_404(session, short_code)
    result = LinkStatsResponse(
        short_code=link.short_code,
        original_url=link.original_url,
        created_at=link.created_at,
        clicks=link.clicks,
        last_used_at=link.last_used_at,
        expires_at=link.expires_at,
        project_id=link.project_id,
    )
    cache.set(f"stats:{short_code}", result, ttl_seconds=60)
    return result


@app.put("/links/{short_code}", response_model=LinkResponse)
def update_link(
    short_code: str,
    payload: LinkUpdate,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    link = get_link_or_404(session, short_code)
    if link.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Можно менять только свои ссылки")
    link.original_url = payload.original_url
    session.add(link)
    session.commit()
    session.refresh(link)
    cache.delete_prefix(f"stats:{short_code}")
    cache.delete_prefix("search:")
    return LinkResponse(
        short_code=link.short_code,
        short_url=build_short_url(request, link.short_code),
        original_url=link.original_url,
        expires_at=link.expires_at,
        project_id=link.project_id,
    )


@app.delete("/links/{short_code}")
def delete_link(
    short_code: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    link = get_link_or_404(session, short_code)
    if link.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Можно удалять только свои ссылки")
    session.delete(link)
    session.commit()
    cache.delete_prefix(f"stats:{short_code}")
    return {"message": "Ссылка удалена"}


@app.get("/expired-links", response_model=list[ExpiredLinkHistoryRead])
def list_expired_links(
    session: Session = Depends(get_session), current_user: User = Depends(get_current_user)
):
    return session.exec(
        select(ExpiredLinkHistory).where(ExpiredLinkHistory.owner_id == current_user.id)
    ).all()


@app.post("/admin/cleanup-policy")
def update_cleanup_policy(
    payload: CleanupConfigRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    set_unused_days_threshold(session, payload.days)
    return {"message": f"Порог очистки обновлен: {payload.days} дней"}


@app.post("/admin/cleanup-run")
def run_cleanup(
    session: Session = Depends(get_session), current_user: User = Depends(get_current_user)
):
    cleanup_expired_links(session)
    cleanup_unused_links(session)
    return {"message": "Очистка выполнена"}
