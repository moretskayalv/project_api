import secrets
import string
from datetime import datetime, timedelta

from sqlmodel import Session, select

from .models import Link, ExpiredLinkHistory, AppConfig

ALPHABET = string.ascii_letters + string.digits


def generate_short_code(length: int = 6) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def unique_short_code(session: Session) -> str:
    while True:
        code = generate_short_code()
        existing = session.exec(select(Link).where(Link.short_code == code)).first()
        if not existing:
            return code


def archive_and_delete_link(session: Session, link: Link, reason: str = "expired"):
    history = ExpiredLinkHistory(
        short_code=link.short_code,
        original_url=link.original_url,
        owner_id=link.owner_id,
        expired_at=datetime.utcnow(),
        clicks=link.clicks,
        created_at=link.created_at,
        last_used_at=link.last_used_at,
        reason=reason,
    )
    session.add(history)
    session.delete(link)


def cleanup_expired_links(session: Session):
    now = datetime.utcnow()
    expired_links = session.exec(select(Link).where(Link.expires_at != None).where(Link.expires_at <= now)).all()
    for link in expired_links:
        archive_and_delete_link(session, link, reason="expired")
    session.commit()


def get_unused_days_threshold(session: Session) -> int:
    config = session.get(AppConfig, "unused_days_threshold")
    return int(config.value) if config else 30


def set_unused_days_threshold(session: Session, days: int):
    config = session.get(AppConfig, "unused_days_threshold")
    if config:
        config.value = str(days)
    else:
        config = AppConfig(key="unused_days_threshold", value=str(days))
        session.add(config)
    session.commit()


def cleanup_unused_links(session: Session):
    threshold = get_unused_days_threshold(session)
    border = datetime.utcnow() - timedelta(days=threshold)
    links = session.exec(select(Link)).all()
    changed = False
    for link in links:
        last_activity = link.last_used_at or link.created_at
        if last_activity <= border:
            archive_and_delete_link(session, link, reason="unused")
            changed = True
    if changed:
        session.commit()
