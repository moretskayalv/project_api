# URL Shortener API

Небольшой REST API сервис для сокращения ссылок, написанный на **FastAPI**.

---

# Функциональность API

### Регистрация пользователя

**POST /auth/register**

Создает нового пользователя и возвращает JWT токен.

Пример запроса:

```json
{
  "username": "alice",
  "email": "alice@example.com",
  "password": "secret123"
}
```

---

### Авторизация

**POST /auth/login**

Позволяет войти в систему и получить JWT токен.

Пример запроса:

```json
{
  "username": "alice",
  "password": "secret123"
}
```

Ответ:

```json
{
  "access_token": "JWT_TOKEN",
  "token_type": "bearer"
}
```

---

### Создание короткой ссылки

**POST /links/shorten**

Создает короткую ссылку для указанного URL.

Пример запроса:

```json
{
  "original_url": "https://google.com",
  "custom_alias": "mygoogle",
  "expires_at": "2026-12-31T23:59:00"
}
```

---

### Редирект по короткой ссылке

**GET /links/{short_code}**

Перенаправляет пользователя на оригинальный URL.
Также увеличивает счетчик переходов.

Пример:

```
GET /links/mygoogle
```

---

### Статистика ссылки

**GET /links/{short_code}/stats**

Возвращает информацию о ссылке:

* original_url
* дата создания
* количество переходов
* время последнего перехода
* дата истечения ссылки

Пример:

```
GET /links/mygoogle/stats
```

---

### Поиск ссылки по оригинальному URL

**GET /links/search**

Позволяет найти короткую ссылку по оригинальному URL.

Пример:

```
GET /links/search?original_url=https://google.com
```

---

### Обновление ссылки

**PUT /links/{short_code}**

Позволяет изменить параметры ссылки.
Изменять можно только ссылки, созданные текущим пользователем.

Пример:

```json
{
  "original_url": "https://python.org"
}
```

---

### Удаление ссылки

**DELETE /links/{short_code}**

Удаляет короткую ссылку.
Удалять можно только свои ссылки.

---

# Структура базы данных

Проект использует **SQLite**.


---

# Запуск проекта

## Локально через Docker

```bash
docker compose up --build
```

Swagger документация будет доступна:

```
http://localhost:8000/docs
```

---

# Деплой

Проект задеплоен на **Render**.

Swagger:

```
https://project-api-tuvg.onrender.com/docs
```
