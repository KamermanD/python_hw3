# FastAPI Link Management Service

Проект представляет собой сервис управления короткими ссылками с поддержкой проектов, пользователей, прав доступа и статистики кликов. Сервис реализован на FastAPI, использует PostgreSQL для хранения данных, Redis для кеширования, и запускается через Docker Compose.

## Deploy

Сервис доступен по ссылке(swager):

https://python-hw3-ozwi.onrender.com/docs

## Структура основного проекта

```
src/
├── api/                # REST API и роутеры
├── auth/               # Аутентификация (FastAPI Users)
├── core/               # Конфигурация, логгер, база данных, middleware, scheduler
├── models/             # SQLAlchemy модели (Link, Project, User)
├── schemas/            # Pydantic схемы
├── services/           # Бизнес-логика (LinkManager, ProjectHandler)
├── utils/              # Утилиты (кэш, локализация времени, демо-данные)
└── main.py             # Точка входа приложения
```

## Основные компоненты

**База данных (PostgreSQL)**

- Таблицы: app_user, link, project_entity, project_members
- Миграции управляются через Alembic
- Данные сохраняются в Docker volume postgres_prod_data

**Кеш (Redis)**

- Используется для хранения:

  - Статистики кликов (clicks_count, last_clicked_at)
  - Данных ссылок для быстрого доступа
  - ACL прав доступа

- TTL кэша: по умолчанию 1 час для ссылок, 5 минут для ACL
- Очистка кэша осуществляется при старте и завершении приложения, а также через Scheduler для устаревших ссылок

**FastAPI**

- REST API для управления ссылками и проектами
- Поддержка аутентификации пользователей через FastAPI Users
- Middleware логирования запросов
- Автоматическая генерация демо-данных через demo_data.py

**Scheduler**

- Проверяет и удаляет устаревшие ссылки
- Обновляет кеш популярных ссылок

## Установка и запуск (Docker)

1. Создайте .env файл с переменными, которые находятся в .env.example

2. Запустите Docker Compose:

docker-compose up --build

3. Контейнеры:

**db** — PostgreSQL (порт 5433 для внешнего доступа)
**redis** — Redis (порт 6380 для внешнего доступа)
**app** — FastAPI (порт 80)
## Описание API

4. Скрипт entrypoint.sh автоматически

- Ждёт готовности БД
- Применяет миграции
- Запускает Gunicorn с Uvicorn worker

## Использование демо-данных

При старте с DB_INIT=true создаются:

**Пользователи:**

- admin@example.com
 / password123
- user1@example.com
 / password123
- user2@example.com
 / password123

- **Проекты:**

- Public (для публичных ссылок)
- User1 Personal Project
- User1 Work Project
- User2 Work Project

**Ссылки:**

- Публичные и приватные ссылки для каждого проекта
- Файл demo_data.py отвечает за генерацию этих данных.


## API

**Ссылки**

- POST /links/ — Создание ссылки
- GET /links/{short_code}/ — Получение ссылки по короткому коду
- PATCH /links/{short_code}/ — Редактирование ссылки
- DELETE /links/{short_code}/ — Удаление ссылки
- GET /links/{short_code}/stats/ — Получение статистики кликов
- GET /links/popular/ — Популярные ссылки
- GET /links/search/ — Поиск ссылок

**Проекты**

- POST /projects/ — Создание проекта
- GET /projects/ — Список проектов пользователя
- PATCH /projects/{id}/ — Изменение проекта
- DELETE /projects/{id}/ — Удаление проекта
- POST /projects/{id}/members/ — Добавление участника
- DELETE /projects/{id}/members/{user_id}/ — Удаление участника

## Кэширование

- Ключи ссылок: link:{short_code}:static и link:{short_code}:stats
- Популярные ссылки: link:popular:{N}
- ACL пользователей: link:{short_code}:acl:{user_uuid}

TTL и логику очистки см. в services/link.py и utils/cache.py.

## Разработка и миграции

alembic revision --autogenerate -m "Описание изменений"
alembic upgrade head

## Примеры использования

**Создание ссылки:**
```
POST /links/
{
  "original_url": "https://example.com",
  "short_code": "exmpl",
  "project_id": 1,
  "is_public": true
}
```
**Получение статистики:**
```
GET /links/exmpl/stats/
```
Ответ:
```
{
  "id": 1,
  "short_code": "exmpl",
  "original_url": "https://example.com",
  "expires_at": "2026-03-21T12:00:00Z",
  "is_public": true,
  "clicks_count": 10,
  "last_clicked_at": "2026-03-20T18:45:00Z"
}
```
## Логирование

- Все ключевые операции логируются через src.core.logger
- Логи включают создание ссылок, клики, удаление и ошибки кэша

## Заметки по продакшену

- Gunicorn + Uvicorn Workers
- Redis используется для ускорения чтения ссылок и уменьшения нагрузки на БД
- Очистка устаревших ссылок и кеша выполняется Scheduler
- Настройка CORS через core.middleware
