import re
import unittest
from unittest.mock import patch

from sqlalchemy.exc import OperationalError

from backend.app import create_app
from backend.database import db
from backend.models import User


class AccountTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "SECRET_KEY": "test-only-secret", "SQLALCHEMY_DATABASE_URI": "sqlite://", "RATELIMIT_ENABLED": False})
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()

    def csrf(self, page="/signup"):
        response = self.client.get(page)
        return re.search(rb'name="csrf_token" value="([^"]+)"', response.data).group(1).decode()

    def signup(self, **extra):
        data = {"name": "Test employee", "email": "commuter@example.com", "address": "1 Example Road", "password": "A long test passphrase!", "confirm_password": "A long test passphrase!", "csrf_token": self.csrf()}
        data.update(extra)
        return self.client.post("/signup", data=data, headers={"Accept": "application/json"})

    def logout(self):
        with self.client.session_transaction() as session:
            token = session["csrf_token"]
        return self.client.post("/logout", data={"csrf_token": token})

    def test_signup_signs_in_employee_and_hashes_password(self):
        response = self.signup(role="ADMIN", email=" Commuter@EXAMPLE.COM ")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"redirect": "/"})
        with self.app.app_context():
            user = db.session.execute(db.select(User)).scalar_one()
            self.assertEqual(user.email, "commuter@example.com")
            self.assertEqual(user.role, "EMPLOYEE")
            self.assertTrue(user.check_password("A long test passphrase!"))
            self.assertNotEqual(user.password_hash, "A long test passphrase!")
        with self.client.session_transaction() as session:
            self.assertIsInstance(session["user_id"], int)
            self.assertNotIn("password", session)
            self.assertNotIn("address", session)
        self.assertIn(b"Test employee", self.client.get("/").data)
        self.assertIn(b"Log out", self.client.get("/").data)
        self.assertNotIn(b"password_hash", response.data)

    def test_login_normalizes_email_and_rotates_csrf(self):
        self.signup()
        self.logout()
        token = self.csrf("/login")
        response = self.client.post("/login", data={"csrf_token": token, "email": "COMMUTER@example.com", "password": "A long test passphrase!"})
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.location, "/")
        with self.client.session_transaction() as session:
            self.assertNotEqual(session["csrf_token"], token)
            self.assertIn("user_id", session)

    def test_invalid_credentials_are_generic(self):
        self.signup()
        self.logout()
        token = self.csrf("/login")
        results = []
        for email in ("commuter@example.com", "missing@example.com"):
            response = self.client.post("/login", data={"csrf_token": token, "email": email, "password": "Wrong password"}, headers={"Accept": "application/json"})
            self.assertEqual(response.status_code, 401)
            results.append(response.json)
        self.assertEqual(results[0], results[1])
        with self.client.session_transaction() as session:
            self.assertNotIn("user_id", session)

    def test_duplicate_email_is_rejected_without_creating_second_user(self):
        self.signup()
        self.logout()
        response = self.signup(email="COMMUTER@example.com")
        self.assertEqual(response.status_code, 409)
        self.assertIn("email", response.json["errors"])
        with self.app.app_context():
            self.assertEqual(db.session.query(User).count(), 1)

    def test_validates_signup_fields_and_password_match(self):
        response = self.signup(name="", address="", email="invalid", password="short", confirm_password="different")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.json["errors"]), {"name", "address", "email", "password", "confirm_password"})
        with self.app.app_context():
            self.assertEqual(db.session.query(User).count(), 0)

    def test_csrf_is_required_for_all_account_posts(self):
        for page in ("/signup", "/login", "/logout"):
            for token in ("", "bad", "非ASCII"):
                response = self.client.post(page, data={"csrf_token": token}, headers={"Accept": "application/json"})
                self.assertEqual(response.status_code, 403)

    def test_logout_requires_post_and_removes_identity(self):
        self.signup()
        self.assertEqual(self.client.get("/logout").status_code, 405)
        response = self.logout()
        self.assertEqual(response.status_code, 303)
        with self.client.session_transaction() as session:
            self.assertNotIn("user_id", session)
        self.assertIn(b"Create account", self.client.get("/").data)

    def test_stale_user_session_becomes_anonymous(self):
        with self.client.session_transaction() as session:
            session["user_id"] = 999
        self.assertEqual(self.client.get("/").status_code, 200)
        with self.client.session_transaction() as session:
            self.assertNotIn("user_id", session)

    def test_session_and_private_page_settings(self):
        response = self.client.get("/signup")
        cookie = response.headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(self.app.permanent_session_lifetime.total_seconds(), 8 * 3600)
        self.assertFalse(self.app.config["SESSION_REFRESH_EACH_REQUEST"])

    def test_auth_pages_do_not_echo_passwords_or_execute_names(self):
        response = self.signup(name='<script>alert(1)</script>', password="tiny", confirm_password="tiny")
        self.assertEqual(response.status_code, 400)
        html = self.client.post("/signup", data={"csrf_token": self.csrf(), "name": '<script>alert(1)</script>', "password": "DO-NOT-ECHO", "email": "invalid"}).data
        self.assertNotIn(b"DO-NOT-ECHO", html)
        self.assertNotIn(b"<script>alert(1)</script>", html)
        self.assertIn(b"&lt;script&gt;", html)

    def test_database_failure_returns_recoverable_error(self):
        token = self.csrf("/login")
        with patch("backend.routes.auth.db.session.execute", side_effect=OperationalError("query", {}, Exception("private-details"))):
            response = self.client.post("/login", data={"csrf_token": token, "email": "commuter@example.com", "password": "A long test passphrase!"}, headers={"Accept": "application/json"})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b"private-details", response.data)

    def test_missing_secret_disables_accounts_but_keeps_dashboard(self):
        self.app.config["SECRET_KEY"] = None
        self.assertEqual(self.client.get("/login").status_code, 503)
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_login_ignores_external_redirect_targets(self):
        self.signup()
        self.logout()
        response = self.client.post("/login?next=https://example.org", data={"csrf_token": self.csrf("/login"), "email": "commuter@example.com", "password": "A long test passphrase!"})
        self.assertEqual(response.location, "/")

    def test_rate_limit_blocks_repeated_login_attempts(self):
        app = create_app({"TESTING": True, "SECRET_KEY": "rate-test-only", "SQLALCHEMY_DATABASE_URI": "sqlite://", "RATELIMIT_ENABLED": True})
        with app.app_context():
            db.create_all()
        client = app.test_client()
        token = re.search(rb'name="csrf_token" value="([^"]+)"', client.get("/login").data).group(1).decode()
        for _ in range(5):
            response = client.post("/login", data={"csrf_token": token, "email": "missing@example.com", "password": "Wrong"}, headers={"Accept": "application/json"})
            self.assertEqual(response.status_code, 401)
        response = client.post("/login", data={"csrf_token": token}, headers={"Accept": "application/json"})
        self.assertEqual(response.status_code, 429)
        self.assertIn("Too many", response.json["error"])
        with app.app_context():
            db.session.remove()
            db.engine.dispose()

    def test_large_form_returns_controlled_error(self):
        token = self.csrf()
        for headers in ({"Accept": "application/json"}, {}):
            response = self.client.post("/signup", data={"csrf_token": token, "name": "X" * 20000}, headers=headers)
            self.assertEqual(response.status_code, 413)
            self.assertIn(b"too large", response.data)

    def test_expired_signed_session_is_not_authenticated(self):
        import time
        self.signup()
        with self.client.session_transaction() as session:
            user_id = session["user_id"]
        serializer = self.app.session_interface.get_signing_serializer(self.app)
        old_time = time.time() - 9 * 3600
        with patch("itsdangerous.timed.time.time", return_value=old_time):
            expired_cookie = serializer.dumps({"user_id": user_id, "_permanent": True})
        self.client.set_cookie("session", expired_cookie)
        html = self.client.get("/").data
        self.assertNotIn(b"Log out", html)
        with self.client.session_transaction() as session:
            self.assertNotIn("user_id", session)

    def test_old_users_without_email_remain_valid_database_records(self):
        with self.app.app_context():
            user = User(name="Existing employee", address="Old Road", role="EMPLOYEE")
            user.set_password("A long test passphrase!")
            db.session.add(user)
            db.session.commit()
            self.assertIsNone(user.email)
        response = self.signup()
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertEqual(db.session.query(User).count(), 2)
