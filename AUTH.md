# ShuttleScope account contract

Employee signup, login and logout support the commuter dashboard. This release creates accounts without granting access to an admin surface or binding them to employee shuttle assignments.

## Identity and data

- Source: `database/schema.sql`, migration `002_user_email.sql`, and `backend/models/User.py`.
- Email is an additive nullable field for compatibility with existing records. New signup requires a syntactically valid email, normalized to lowercase with an ASCII domain; a database index on LOWER(email) prevents case-insensitive duplicates, including simultaneous signups. Syntax validation does not verify email ownership.
- Existing records without email remain unchanged and cannot use email login until provisioned separately. No account claiming or linking by name/address is allowed.
- Signup takes name (1–100 characters), email (up to 254), address (1–500), password and confirmation. Leading/trailing whitespace is stripped from name/email/address, never from passwords. Address collection follows the existing required users.address column; it is not exposed in session cookies or returned by login.
- Passwords are salted scrypt hashes. Signup accepts 15–128 characters, matching OWASP's length guidance for accounts without MFA; composition rules are not added. Source: https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html. This implementation does not yet screen passwords against a breached-password blocklist.
- Signup fixes role to EMPLOYEE on the server regardless of client input. ADMIN exists in the database but has no signup or administrative UI in this release.

## Session and request rules

- Flask signed cookies store user ID, CSRF token and permanence metadata, never password hashes, email or address. Identity is reloaded from the database for account/page requests; a missing user clears the session. Map APIs remain public and do not query identity.
- Success clears previous session state, sets user ID, rotates CSRF and returns to `/`; arbitrary `next` targets are ignored. The maximum session lifetime is eight hours, with refresh on every request disabled.
- POST signup/login/logout require a session-bound CSRF token checked with a constant-time comparison. Logout is never a GET action. The dashboard header reuses the same CSRF owner as account screens.
- `SESSION_SECRET` is private local/production configuration. The previously tracked SECRET_KEY variable is not trusted for sessions. Missing session configuration fails closed for accounts while preserving public map functionality.
- Cookies are HttpOnly and SameSite=Lax. Production requires HTTPS and SESSION_COOKIE_SECURE=true. HTML/account responses are not cached.
- Flask-Limiter limits signup and login to five POST requests/minute per remote client address. Forwarded addresses are not implicitly trusted. Local memory storage is per-process; shared storage with an appropriate driver/proxy deployment configuration is required before multi-worker production.
- Signed cookies are cleared on this browser's logout but are not backed by a revocable server-side session store. Password reset, account blocking, all-device logout and stolen-cookie revocation must add that capability before those features ship.

## Flows and recovery

- GET `/signup` and `/login` render native semantic forms. POSTs accept form data and return a 303 redirect on success; clients requesting application/json receive an error object or `{redirect:"/"}`. These are not JSON-body APIs.
- Invalid signup fields return 400; duplicate email returns 409 with email recovery guidance. Invalid login always returns the same 401 message for unknown emails and incorrect passwords, with a dummy scrypt verification for unknown accounts. Rate limits return 429; database errors return 503 without leaking database details. Account POST bodies are limited to 16 KiB.
- Frontend validation, first-error focus, visible password toggle, password-manager autocomplete and paste are supported. JS adds pending/duplicate prevention and inline timeout/offline/server recovery. Native forms remain usable without JS.
- Passwords are not echoed into server-rendered errors. Invalid login clears the password and preserves email. A network failure while creating an account explains that the operation may have succeeded and suggests trying login before retrying signup.
- Email verification, password reset, admin authorization, account deletion and shuttle-route assignment are outside this change. No email messages are sent.
