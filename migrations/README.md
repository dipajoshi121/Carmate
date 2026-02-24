# Database migrations

- **001_schema.sql** – Creates all Carmate tables (safe to re-run; uses `IF NOT EXISTS`).

## Tables

| Table | Purpose |
|-------|--------|
| `users` | Login, register, update profile, view users |
| `password_reset_tokens` | Forgot password flow |
| `service_requests` | My requests, create request, request details, submit estimate |
| `service_request_photos` | Upload vehicle photos (stores file path per request) |

## Run migration

1. Set `DATABASE_URL` (Neon connection string).
2. From project root:
   ```bash
   python run_migration.py
   ```
   Or in Neon SQL Editor: paste and run the contents of `001_schema.sql`.

## Using the DB from code

Use `src/db.py`. It expects `DATABASE_URL` in the environment.

- **Users:** `create_user`, `get_user_by_email`, `get_user_by_id`, `verify_password`, `update_user`, `list_users`, `set_user_active`
- **Password reset:** `create_password_reset_token`, `user_exists_by_email`, `get_valid_reset_token`, `mark_reset_token_used`
- **Service requests:** `create_service_request`, `get_my_requests`, `get_request_by_id`, `update_request_estimate`, `update_estimate_status`
- **Photos:** `add_request_photo`
