-- Existing rows keep NULL email until the owner assigns a verified login address.
BEGIN;
ALTER TABLE users ADD COLUMN IF NOT EXISTS email TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS users_email_unique ON users (LOWER(email));
COMMIT;
