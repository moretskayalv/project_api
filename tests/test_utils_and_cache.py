from __future__ import annotations

from datetime import datetime, timedelta

from sqlmodel import Session

from app.cache import TTLCache
from app.models import AppConfig, ExpiredLinkHistory, Link
from app.utils import (
    archive_and_delete_link,
    cleanup_expired_links,
    cleanup_unused_links,
    generate_short_code,
    get_unused_days_threshold,
    set_unused_days_threshold,
    unique_short_code,
)


def test_generate_short_code_default_length_and_alphabet():
    code = generate_short_code()
    assert len(code) == 6
    assert code.isalnum()


def test_unique_short_code_retries_until_free(session, monkeypatch):
    busy = Link(short_code='taken01', original_url='https://busy.example')
    session.add(busy)
    session.commit()

    generated = iter(['taken01', 'free02'])
    monkeypatch.setattr('app.utils.generate_short_code', lambda length=6: next(generated))

    assert unique_short_code(session) == 'free02'


def test_archive_and_delete_link_creates_history_record(session):
    link = Link(short_code='archive01', original_url='https://archive.example', clicks=3)
    session.add(link)
    session.commit()
    session.refresh(link)

    archive_and_delete_link(session, link, reason='unused')
    session.commit()

    history = session.query(ExpiredLinkHistory).one()
    assert history.short_code == 'archive01'
    assert history.reason == 'unused'
    assert session.get(Link, link.id) is None


def test_cleanup_expired_links_moves_only_expired_links(session):
    expired = Link(
        short_code='expired01',
        original_url='https://expired.example',
        expires_at=datetime.utcnow() - timedelta(days=1),
    )
    active = Link(
        short_code='active01',
        original_url='https://active.example',
        expires_at=datetime.utcnow() + timedelta(days=1),
    )
    session.add(expired)
    session.add(active)
    session.commit()

    cleanup_expired_links(session)

    assert session.query(Link).filter(Link.short_code == 'expired01').first() is None
    assert session.query(Link).filter(Link.short_code == 'active01').first() is not None
    history = session.query(ExpiredLinkHistory).one()
    assert history.reason == 'expired'


def test_default_unused_days_threshold_is_30(session):
    assert get_unused_days_threshold(session) == 30


def test_set_unused_days_threshold_creates_and_updates_config(session):
    set_unused_days_threshold(session, 7)
    assert get_unused_days_threshold(session) == 7

    set_unused_days_threshold(session, 15)
    assert get_unused_days_threshold(session) == 15
    config = session.get(AppConfig, 'unused_days_threshold')
    assert config.value == '15'


def test_cleanup_unused_links_archives_old_records(session):
    set_unused_days_threshold(session, 5)
    old_link = Link(
        short_code='old001',
        original_url='https://old.example',
        created_at=datetime.utcnow() - timedelta(days=10),
    )
    fresh_link = Link(
        short_code='fresh1',
        original_url='https://fresh.example',
        created_at=datetime.utcnow(),
    )
    session.add(old_link)
    session.add(fresh_link)
    session.commit()

    cleanup_unused_links(session)

    assert session.query(Link).filter(Link.short_code == 'old001').first() is None
    assert session.query(Link).filter(Link.short_code == 'fresh1').first() is not None
    history = session.query(ExpiredLinkHistory).one()
    assert history.reason == 'unused'


def test_ttl_cache_expires_records(monkeypatch):
    cache = TTLCache()
    current_time = {'value': 100.0}

    monkeypatch.setattr('app.cache.time.time', lambda: current_time['value'])
    cache.set('key', 'value', ttl_seconds=10)
    assert cache.get('key') == 'value'

    current_time['value'] = 111.0
    assert cache.get('key') is None


def test_ttl_cache_delete_prefix():
    cache = TTLCache()
    cache.set('stats:one', 1)
    cache.set('stats:two', 2)
    cache.set('search:one', 3)

    cache.delete_prefix('stats:')

    assert cache.get('stats:one') is None
    assert cache.get('stats:two') is None
    assert cache.get('search:one') == 3
