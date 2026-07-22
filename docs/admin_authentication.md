# Admin authentication

Phase 3 provides a local administrative boundary. It is suitable for local development and manual data curation, not public registration or internet deployment.

## Account lifecycle and passwords

Usernames are trimmed, lower-cased, and unique. Accounts are `active`, `disabled`, or temporarily `locked`. Passwords are at least 12 characters, reject common examples, and are hashed with pwdlib's recommended Argon2 implementation. Raw passwords are accepted only by the login request or secure CLI prompt and are never stored, returned, or audited. A dummy hash verification prevents a simple username-enumeration timing path.

Create an account with `python -m backend.admin_cli create-admin`. `list-admins` shows only public ID, username, display name, and status. `disable-admin` revokes sessions; `enable-admin` restores access; `reset-password` replaces the hash and revokes all existing sessions. Security-sensitive commands confirm interactively, and password values are never command-line arguments.

## Sessions, lockout, and logout

Successful login creates cryptographically random session and CSRF values. Only SHA-256 hashes are stored. The session token is sent as an HttpOnly, SameSite=Strict cookie; its Secure flag is configurable and must be enabled with HTTPS. Sessions expire after the configured TTL, track last use, and can be revoked. Logout revokes server state and clears cookies. Password reset and account disable also revoke sessions.

Failed logins increment a database counter. At the configured threshold the account is temporarily locked. Login always returns a generic invalid-credentials error, including for missing, disabled, or locked accounts. Success, failure, lockout, logout, and rejected sessions are audited without credential material.

## CSRF design

Safe GET requests need only the valid session. After login, the dashboard calls `GET /api/admin/auth/csrf`, keeps the returned value only in page memory, and includes it in the configured header for every mutation. The server requires the header to match the CSRF cookie and the stored hash using timing-safe comparisons. Missing or mismatched values return a controlled 403.

## Recovery and limitations

If all sessions are unusable, stop public access to the local service and use `reset-password` or `enable-admin` from the project environment. There is no email recovery, MFA, roles, federated identity, cross-device session UI, distributed rate limiter, or production reverse-proxy hardening in Phase 3.
