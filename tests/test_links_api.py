from __future__ import annotations

from datetime import datetime, timedelta


def test_create_link_with_custom_alias_for_authorized_user(client, auth_headers):
    response = client.post(
        '/links/shorten',
        json={
            'original_url': 'https://example.com',
            'custom_alias': 'example-alias',
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body['short_code'] == 'example-alias'
    assert body['original_url'] == 'https://example.com'
    assert body['short_url'].endswith('/links/example-alias')


def test_create_public_link_without_auth(client):
    response = client.post(
        '/links/shorten',
        json={'original_url': 'https://public.example'},
    )

    assert response.status_code == 201
    assert response.json()['project_id'] is None


def test_create_link_rejects_invalid_url(client):
    response = client.post(
        '/links/shorten',
        json={'original_url': 'ftp://example.com'},
    )

    assert response.status_code == 422


def test_custom_alias_must_be_unique(client, auth_headers):
    first = client.post(
        '/links/shorten',
        json={'original_url': 'https://example.com', 'custom_alias': 'same-alias'},
        headers=auth_headers,
    )
    assert first.status_code == 201

    second = client.post(
        '/links/shorten',
        json={'original_url': 'https://python.org', 'custom_alias': 'same-alias'},
        headers=auth_headers,
    )
    assert second.status_code == 400
    assert second.json()['detail'] == 'custom_alias уже занят'


def test_create_link_with_project_requires_auth(client):
    response = client.post(
        '/links/shorten',
        json={'original_url': 'https://example.com', 'project_id': 1},
    )

    assert response.status_code == 401
    assert 'авторизованному пользователю' in response.json()['detail']


def test_create_link_with_existing_project(client, auth_headers):
    project = client.post('/projects', json={'name': 'Docs'}, headers=auth_headers)
    project_id = project.json()['id']

    response = client.post(
        '/links/shorten',
        json={
            'original_url': 'https://example.com/docs',
            'project_id': project_id,
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    assert response.json()['project_id'] == project_id


def test_create_link_with_foreign_project_returns_404(client, auth_headers, second_auth_headers):
    project = client.post('/projects', json={'name': 'Private'}, headers=second_auth_headers)
    project_id = project.json()['id']

    response = client.post(
        '/links/shorten',
        json={
            'original_url': 'https://example.com/private',
            'project_id': project_id,
        },
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert response.json()['detail'] == 'Проект не найден'


def test_search_returns_found_result_and_uses_cache(client, auth_headers):
    created = client.post(
        '/links/shorten',
        json={'original_url': 'https://searchable.example', 'custom_alias': 'search-me'},
        headers=auth_headers,
    )
    assert created.status_code == 201

    response = client.get('/links/search', params={'original_url': 'https://searchable.example'})
    assert response.status_code == 200
    assert response.json() == {
        'found': True,
        'short_code': 'search-me',
        'original_url': 'https://searchable.example',
    }


def test_search_returns_not_found_result(client):
    response = client.get('/links/search', params={'original_url': 'https://missing.example'})
    assert response.status_code == 200
    assert response.json() == {
        'found': False,
        'short_code': None,
        'original_url': None,
    }


def test_redirect_increments_clicks_and_returns_307(client, auth_headers):
    client.post(
        '/links/shorten',
        json={'original_url': 'https://redirect.example', 'custom_alias': 'go-there'},
        headers=auth_headers,
    )

    response = client.get('/links/go-there', follow_redirects=False)
    assert response.status_code == 307
    assert response.headers['location'] == 'https://redirect.example'

    stats = client.get('/links/go-there/stats')
    body = stats.json()
    assert body['clicks'] == 1
    assert body['last_used_at'] is not None


def test_stats_return_404_for_missing_link(client):
    response = client.get('/links/unknown/stats')
    assert response.status_code == 404
    assert response.json()['detail'] == 'Короткая ссылка не найдена'


def test_expired_link_is_deleted_on_stats_read(client, auth_headers):
    expired_at = (datetime.utcnow() - timedelta(minutes=1)).isoformat()
    create = client.post(
        '/links/shorten',
        json={
            'original_url': 'https://expired.example',
            'custom_alias': 'expired-link',
            'expires_at': expired_at,
        },
        headers=auth_headers,
    )
    assert create.status_code == 201

    response = client.get('/links/expired-link/stats')
    assert response.status_code == 404
    assert response.json()['detail'] == 'Короткая ссылка не найдена'


def test_update_link_changes_original_url(client, auth_headers):
    created = client.post(
        '/links/shorten',
        json={'original_url': 'https://before.example', 'custom_alias': 'editable'},
        headers=auth_headers,
    )
    assert created.status_code == 201

    response = client.put(
        '/links/editable',
        json={'original_url': 'https://after.example'},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()['original_url'] == 'https://after.example'


def test_update_link_forbidden_for_non_owner(client, auth_headers, second_auth_headers):
    client.post(
        '/links/shorten',
        json={'original_url': 'https://owner.example', 'custom_alias': 'owners-only'},
        headers=auth_headers,
    )

    response = client.put(
        '/links/owners-only',
        json={'original_url': 'https://hacker.example'},
        headers=second_auth_headers,
    )

    assert response.status_code == 403
    assert response.json()['detail'] == 'Можно менять только свои ссылки'


def test_delete_link_forbidden_for_non_owner(client, auth_headers, second_auth_headers):
    client.post(
        '/links/shorten',
        json={'original_url': 'https://delete.example', 'custom_alias': 'delete-me'},
        headers=auth_headers,
    )

    response = client.delete('/links/delete-me', headers=second_auth_headers)
    assert response.status_code == 403
    assert response.json()['detail'] == 'Можно удалять только свои ссылки'


def test_delete_link_success(client, auth_headers):
    client.post(
        '/links/shorten',
        json={'original_url': 'https://delete.example', 'custom_alias': 'delete-ok'},
        headers=auth_headers,
    )

    response = client.delete('/links/delete-ok', headers=auth_headers)
    assert response.status_code == 200
    assert response.json()['message'] == 'Ссылка удалена'

    stats = client.get('/links/delete-ok/stats')
    assert stats.status_code == 404


def test_expired_links_history_and_cleanup_admin_endpoints(client, auth_headers):
    expired_at = (datetime.utcnow() - timedelta(minutes=1)).isoformat()
    create = client.post(
        '/links/shorten',
        json={
            'original_url': 'https://history.example',
            'custom_alias': 'history-link',
            'expires_at': expired_at,
        },
        headers=auth_headers,
    )
    assert create.status_code == 201

    trigger_cleanup = client.post('/admin/cleanup-run', headers=auth_headers)
    assert trigger_cleanup.status_code == 200

    history = client.get('/expired-links', headers=auth_headers)
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]['reason'] == 'expired'


def test_cleanup_policy_update(client, auth_headers):
    response = client.post('/admin/cleanup-policy', json={'days': 10}, headers=auth_headers)
    assert response.status_code == 200
    assert '10 дней' in response.json()['message']
