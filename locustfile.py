from __future__ import annotations

from random import randint

from locust import HttpUser, between, task


class ShortenerUser(HttpUser):
    wait_time = between(1, 2)

    def on_start(self):
        suffix = randint(1000, 9999)
        self.username = f'load_{suffix}'
        self.password = 'secret123'
        register = self.client.post(
            '/auth/register',
            json={
                'username': self.username,
                'email': f'{self.username}@example.com',
                'password': self.password,
            },
            name='auth_register',
        )
        self.token = register.json().get('access_token') if register.ok else None
        self.headers = {'Authorization': f'Bearer {self.token}'} if self.token else {}

    @task(3)
    def create_short_link(self):
        suffix = randint(10000, 99999)
        self.client.post(
            '/links/shorten',
            json={
                'original_url': f'https://example.com/{suffix}',
                'custom_alias': f'load-{suffix}',
            },
            headers=self.headers,
            name='create_short_link',
        )

    @task(1)
    def search_link(self):
        self.client.get(
            '/links/search',
            params={'original_url': 'https://example.com/healthcheck'},
            name='search_link',
        )
