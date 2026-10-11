# api-server-fastapi

A FastAPI and SQLModel API boilerplate demonstrating authentication, ownership,
relationships, pagination, profiles, and role-based access control. The current
storage layer is SQLite plus local disk for development.

## Configuration

Copy `.env.example` to `.env` and provide the required secrets. Passwords are
sent as JSON over HTTPS and hashed with Argon2 on the server. Do not place shared
secrets in frontend configuration: browser-delivered values are not secret.

The application currently creates tables at startup with SQLModel. Add Alembic
before using this schema-change strategy in production.

## Authentication

Registration is a two-step development flow:

1. `POST /auth/register/email` with `{"email": "user@example.com"}` returns a
   signed, short-lived registration token. A production email provider should
   deliver this token instead of returning it from the API.
2. `POST /auth/register/password` with `{"email", "password", "token"}` creates
   the account and hashes the password.

The rest of the auth surface is:

- `POST /auth/login`: creates an access-token and refresh-token session.
- `POST /auth/refresh`: rotates a refresh token and revokes the old session.
- `POST /auth/logout`: revokes the current session.
- `POST /auth/logout-everywhere`: revokes every active session.
- `GET /auth/sessions`: lists active devices/sessions.
- `POST /auth/verify-email/request` and `POST /auth/verify-email`.
- `POST /auth/forgot-password` and `POST /auth/reset-password`.
- `POST /auth/change-password`.
- `POST /auth/oauth/link` and `DELETE /auth/oauth/{provider}`.

One-time tokens are stored hashed and are single-use. The current development
responses expose verification and reset tokens so the flow can be tested without
an email provider; production should send them through a background email task.

## Users and profiles

- `GET/PATCH/DELETE /users/me`
- `PATCH /users/me/profile`
- `POST /users/me/avatar` stores an upload through the local storage abstraction.
- `GET /users/` lists users for admins with search and offset pagination.
- `PATCH /users/{user_id}/active` deactivates or activates a user.
- `PATCH /users/{user_id}/role` changes `user`/`admin` roles.

Deleting the current user anonymizes the email, removes the password, marks the
user inactive, and records `deleted_at`. Admin routes require the `admin` role.

## Items

Items are owned by users and support soft deletion:

- `POST/GET /items/`
- `GET/PATCH/DELETE /items/{item_id}`
- `POST/GET /items/{item_id}/descriptions`
- `DELETE /items/{item_id}/descriptions/{description_id}`

The collection endpoint supports `limit`, `offset`, `sort_by`, `sort_order`,
`status`, and `search`. Item access is restricted to the owner, except for
admins. `ItemDescription` is a one-to-many related resource that can represent
versions or translations.

## System endpoints

- `GET /health` checks that the process is running.
- `GET /ready` is the deployment readiness endpoint.

Responses for validation and HTTP errors include an `error` object and request ID.
Every response also includes the `X-Request-ID` header. The request middleware
logs method, path, status, and request ID without logging passwords or tokens.

Rate limiting, S3 storage, Alembic migrations, and an external email provider
remain intentionally outside this local-only implementation. They are the next
production integration boundaries.
