# Plan: User Accounts (Phased)

## Context

HomeBidder is currently a fully public FastAPI + React app — no authentication, all analyses are visible to everyone, rate limiting is IP-based only. The feature adds optional user accounts so that analyses can be tied to an owner, users can manage their history, and the app can support higher quotas for registered users. Social login (Google) avoids password friction. Implementation is phased so each phase is independently shippable and testable.

---

## Phase 1 — Backend Auth Foundation

**Goal**: Users can register and log in with email/password. JWT tokens are issued. Existing public endpoints are unaffected.

### New dependency: `fastapi-users[sqlalchemy]>=13.0` + `httpx-oauth>=0.15` + `python-multipart>=0.0.9`

Add to `/backend/requirements.txt`.

### DB schema changes

**`/backend/db/models.py`**

Add `User` model using fastapi-users' `SQLAlchemyBaseUserTableUUID` mixin:
```python
class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "users"
    display_name: Mapped[str | None] = mapped_column(String(128))
```

Add nullable FK to `Analysis`:
```python
user_id: Mapped[uuid.UUID | None] = mapped_column(
    Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
)
```

**`/backend/db/__init__.py`**

Add `("user_id", "VARCHAR(36)")` to the `_ANALYSES_MIGRATIONS` list (existing migration pattern). New `users` table is created automatically via `create_all`.

Add Pydantic schemas `UserRead`, `UserCreate`, `UserUpdate` in `models.py` (fastapi-users requires them).

### New files

**`/backend/db/user_manager.py`** — fastapi-users `UserManager` class + `get_user_db` / `get_user_manager` dependencies.

**`/backend/api/auth.py`** — wires up `BearerTransport` + `JWTStrategy` + `FastAPIUsers` instance. Exports:
- `current_active_user` — raises 401 if unauthenticated
- `current_optional_user` — returns `None` if unauthenticated (used on public endpoints)

### Register routers in `/backend/main.py`

Auto-generated endpoints:
- `POST /api/auth/jwt/login` — returns `access_token`
- `POST /api/auth/jwt/logout`
- `POST /api/auth/register`
- `POST /api/auth/forgot-password` / `POST /api/auth/reset-password`
- `GET /api/users/me` / `PATCH /api/users/me`

### Config changes — `/backend/config.py`

New settings:
- `jwt_secret` property — reads `JWT_SECRET` env var (required; add to startup validation)
- `rate_limit_authenticated_per_day` — reads `RATE_LIMIT_AUTHENTICATED_PER_DAY` (default 20)

### Rate limiter update — `/backend/api/rate_limit.py`

Inject `current_optional_user`. When `user is not None`: use `str(user.id)` as identifier with `RATE_LIMIT_AUTHENTICATED_PER_DAY` limit. Anonymous: unchanged (hashed IP, `RATE_LIMIT_ANALYSES_PER_DAY`).

### Tests (write before implementation)

**New: `/backend/tests/api/test_auth.py`**
- `test_register_creates_user`
- `test_register_duplicate_email_returns_400`
- `test_login_returns_access_token`
- `test_login_wrong_password_returns_400`
- `test_me_returns_user_when_authenticated`
- `test_me_returns_401_when_unauthenticated`
- `test_analyze_still_works_unauthenticated` (regression)

**New: `/backend/tests/db/test_user_model.py`**
- `test_user_table_exists_after_init_db`
- `test_analyses_user_id_column_is_nullable`

**Extend: `/backend/tests/api/test_rate_limit.py`**
- `test_authenticated_user_not_blocked_by_ip_limit`
- `test_authenticated_user_limited_by_account_quota`
- `test_authenticated_uses_user_id_not_ip`

### Env vars added in Phase 1

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `JWT_SECRET` | Yes | — | Signs JWT tokens (32+ random bytes) |
| `RATE_LIMIT_AUTHENTICATED_PER_DAY` | No | 20 | Daily quota for logged-in users |

---

## Phase 2 — Wire User into Analysis Flow + Frontend Auth

**Goal**: Analyses are tied to the logged-in user. Frontend has login/register/logout UI. History is scoped per-user.

### Backend changes

**`/backend/api/routes.py`**

- `analyze_listing`: inject `current_optional_user`, pass `user_id` down to `run_agent`
- `list_analyses`: if `user` → filter `Analysis.user_id == user.id`; if anon → filter `user_id IS NULL`
- `delete_analysis`: ownership check — authed users can only delete their own; anon can only delete null-user analyses

**`/backend/agent/orchestrator.py`**

- `run_agent(...)` gains `user_id: uuid.UUID | None = None` param
- `_persist_analysis(...)` sets `analysis.user_id = user_id`

### Frontend new files

**`/frontend/src/lib/auth.ts`** — typed helpers: `getToken`, `setToken`, `clearToken`, `authHeaders`, `login`, `register`, `logout`, `fetchCurrentUser`

**`/frontend/src/lib/AuthContext.tsx`** — React Context with `user`, `token`, `isLoading`, `login`, `register`, `logout`. On mount: read token from localStorage, validate against `/api/users/me`, clear if stale.

**`/frontend/src/routes/login.tsx`** — email/password form, calls `auth.login()`, navigates to `/` on success, links to `/register`

**`/frontend/src/routes/register.tsx`** — email/password form, calls `auth.register()` + auto-login, navigates to `/`

### Frontend file modifications

**`/frontend/src/routes/__root.tsx`** — wrap children with `<AuthProvider>`

**`/frontend/src/components/Header.tsx`** — use `useAuth()`: show Login/Sign up when anonymous; show email abbreviation, Profile link, and Logout when authenticated

**`/frontend/src/routes/analysis.tsx`** and **`/frontend/src/routes/history.tsx`** — add `authHeaders()` to all `fetch` calls

### Tests (write before implementation)

**New: `/backend/tests/api/test_auth_analysis.py`**
- `test_analyze_with_auth_sets_user_id`
- `test_analyze_without_auth_user_id_is_null`
- `test_list_analyses_authenticated_returns_only_own`
- `test_list_analyses_unauthenticated_returns_only_anonymous`
- `test_delete_own_analysis_succeeds_204`
- `test_delete_others_analysis_returns_403`

**New frontend tests (colocated):**
- `/frontend/src/lib/auth.test.ts` — token helpers and authHeaders
- `/frontend/src/lib/AuthContext.test.tsx` — init, login, logout, stale-token clearing
- `/frontend/src/routes/login.test.tsx` — renders, submits, error, navigates, links to register
- `/frontend/src/routes/register.test.tsx` — renders, submits, error, navigates
- `/frontend/src/components/Header.test.tsx` (extend) — shows correct links for authed vs anon

---

## Phase 3 — Profile Page

**Goal**: Authenticated users can view their account, change their password, and delete their account.

### Backend changes

**New: `/backend/api/profile.py`**

`DELETE /api/users/me` — calls `user_manager.delete(user)`. FK `ON DELETE SET NULL` on `analyses.user_id` orphans the user's analyses (they become anonymous).

Register `profile_router` in `/backend/main.py`.

Change password uses the existing fastapi-users `PATCH /api/users/me` with `{ "password": "..." }`.

### Frontend new file

**`/frontend/src/routes/profile.tsx`**

Route at `/profile`. Redirects to `/login?next=/profile` if not authenticated.

Sections:
1. Account info — email display (read-only)
2. Change password — new password + confirm form → `PATCH /api/users/me`
3. Danger zone — "Delete account" button with confirmation step (type "DELETE" or modal) → `DELETE /api/users/me` → clear token → redirect to `/`

### Tests (write before implementation)

**New: `/backend/tests/api/test_profile.py`**
- `test_delete_me_removes_user`
- `test_delete_me_returns_401_when_unauthenticated`
- `test_delete_me_sets_analyses_user_id_to_null`

**New: `/frontend/src/routes/profile.test.tsx`**
- redirects when not authed
- renders email when authed
- change password form calls PATCH
- delete confirmation prompt
- calls DELETE and navigates on confirm

---

## Phase 4 — Social Logins (Google OAuth2)

**Goal**: "Continue with Google" on login/register pages. Apple and Facebook use the same pattern and can be added by repeating this phase.

### DB schema change

**`/backend/db/models.py`**

Add `OAuthAccount` model using fastapi-users' `SQLAlchemyBaseOAuthAccountTableUUID`:
```python
class OAuthAccount(SQLAlchemyBaseOAuthAccountTableUUID, Base):
    __tablename__ = "oauth_accounts"
```

Update `User` to include `oauth_accounts: Mapped[list["OAuthAccount"]]` relationship. Update `get_user_db` to pass `OAuthAccount`. New table created automatically by `create_all`.

### New backend file: `/backend/api/oauth.py`

Creates `GoogleOAuth2` client from `httpx_oauth.clients.google`. Registers `fastapi_users.get_oauth_router(google_oauth_client, ...)` at `/api/auth/google`.

New routes:
- `GET /api/auth/google/authorize` → returns `{ "authorization_url": "..." }`
- `GET /api/auth/google/callback` → returns JWT token

Register router in `/backend/main.py`.

### Config changes — `/backend/config.py`

New properties: `google_client_id`, `google_client_secret`, `google_redirect_url`.

### Frontend changes

**New: `/frontend/src/routes/auth/callback/google.tsx`**

Handles `?code=...&state=...` from Google redirect. Calls `/api/auth/google/callback`, stores JWT, updates auth context, navigates to `/`.

**Update login + register pages** — "Continue with Google" button → fetches `/api/auth/google/authorize` → `window.location.href = authorization_url`.

### Tests (write before implementation)

**New: `/backend/tests/api/test_oauth.py`** — mock `httpx_oauth` token exchange:
- `test_google_authorize_returns_authorization_url`
- `test_google_callback_creates_user_on_first_login`
- `test_google_callback_logs_in_existing_user`
- `test_google_callback_with_invalid_state_returns_400`

**New: `/frontend/src/routes/auth/callback/google.test.tsx`**
- renders loading state
- calls backend callback URL with code/state
- stores token and navigates to / on success
- shows error on failure

**Extend: `/frontend/src/routes/login.test.tsx`**
- renders Continue with Google button
- clicking it calls /api/auth/google/authorize and redirects

### New env vars added in Phase 4

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `GOOGLE_CLIENT_ID` | For Google OAuth | "" | Google Cloud Console OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | For Google OAuth | "" | Google Cloud Console OAuth client secret |
| `GOOGLE_REDIRECT_URL` | No | `http://localhost:3000/auth/callback/google` | Must match Google Console's authorized redirect URI |

---

## Key Design Notes

- **No breaking changes**: `current_optional_user` returns `None` when no Bearer token is present. Unauthenticated flows continue to work unchanged.
- **`session_id` field**: Already nullable, already unused. Leave it alone (SQLite pre-3.35 cannot drop columns). `user_id` serves the auth purpose.
- **TanStack file-based routing**: New routes just need a `.tsx` file in `routes/` — `routeTree.gen.ts` auto-regenerates when Vite runs.
- **Email verification**: fastapi-users' verify router is included, but sending the email requires an SMTP/SendGrid integration. For Phase 1, log the token in `on_after_register`. Wire real email later.
- **JWT storage**: `localStorage`. App is a cross-origin SPA; httpOnly cookies require `SameSite=None; Secure` and `credentials: 'include'` everywhere. localStorage is simpler for this context.

## Verification (end-to-end)

After each phase:
```bash
# Backend
cd backend && python3 -m pytest tests/ -v

# Frontend
cd frontend && npm test
```

Manual flows:
- **Phase 1**: `curl` register → login → `/api/users/me`
- **Phase 2**: Log in, run analysis, verify `user_id` is set in DB; open incognito, run analysis, verify `user_id` is NULL; check `/history` scoping
- **Phase 3**: Change password → log out → log back in with new password; delete account → verify analyses become anonymous
- **Phase 4**: Click "Continue with Google" → complete Google flow → verify JWT issued and user created in DB
