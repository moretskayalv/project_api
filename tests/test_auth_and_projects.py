from __future__ import annotations


def test_register_returns_token(client):
    response = client.post(
        '/auth/register',
        json={
            'username': 'alice',
            'email': 'alice@example.com',
            'password': 'secret123',
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body['access_token']
    assert body['token_type'] == 'bearer'


def test_register_rejects_duplicate_username_or_email(client, registered_user):
    response = client.post(
        '/auth/register',
        json={
            'username': 'alice',
            'email': 'another@example.com',
            'password': 'secret123',
        },
    )
    assert response.status_code == 400
    assert 'уже существует' in response.json()['detail']

    response = client.post(
        '/auth/register',
        json={
            'username': 'another',
            'email': 'alice@example.com',
            'password': 'secret123',
        },
    )
    assert response.status_code == 400


def test_login_success(client, registered_user):
    response = client.post(
        '/auth/login',
        json={'username': 'alice', 'password': 'secret123'},
    )

    assert response.status_code == 200
    assert response.json()['token_type'] == 'bearer'


def test_login_rejects_bad_password(client, registered_user):
    response = client.post(
        '/auth/login',
        json={'username': 'alice', 'password': 'wrong-password'},
    )

    assert response.status_code == 401
    assert response.json()['detail'] == 'Неверные учетные данные'


def test_projects_require_auth(client):
    response = client.get('/projects')
    assert response.status_code == 401
    assert response.json()['detail'] == 'Требуется авторизация'


def test_create_and_list_only_own_projects(client, auth_headers, second_auth_headers):
    create_first = client.post('/projects', json={'name': 'Main project'}, headers=auth_headers)
    create_second = client.post('/projects', json={'name': 'Bob project'}, headers=second_auth_headers)

    assert create_first.status_code == 201
    assert create_second.status_code == 201

    response = client.get('/projects', headers=auth_headers)
    assert response.status_code == 200
    assert [project['name'] for project in response.json()] == ['Main project']
