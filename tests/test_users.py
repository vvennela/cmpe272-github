import unittest

from flask import Flask
from sqlalchemy import text
from sqlalchemy.exc import StatementError
from werkzeug.security import check_password_hash

from backend.database import db
from backend.models import User


class UserModelTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI="sqlite://")
        db.init_app(self.app)
        context = self.app.app_context()
        context.push()
        self.addCleanup(context.pop)
        db.create_all()
        self.addCleanup(db.engine.dispose)
        self.addCleanup(db.session.remove)

    def new_user(self):
        return User(name="Test employee", address="1 Test Road")

    def test_hashes_password_and_checks_correct_and_incorrect_values(self):
        user = self.new_user()
        user.set_password("Example password 123!")
        self.assertNotEqual(user.password_hash, "Example password 123!")
        self.assertTrue(check_password_hash(user.password_hash, "Example password 123!"))
        self.assertTrue(user.check_password("Example password 123!"))
        self.assertFalse(user.check_password("Wrong password"))
        self.assertNotIn("Example password 123!", repr(user))
        self.assertNotIn("password", user.__dict__)

    def test_identical_passwords_have_different_salts(self):
        first, second = self.new_user(), self.new_user()
        first.set_password("Same password")
        second.set_password("Same password")
        self.assertNotEqual(first.password_hash, second.password_hash)
        self.assertTrue(first.check_password("Same password"))
        self.assertTrue(second.check_password("Same password"))

    def test_password_change_invalidates_old_password(self):
        user = self.new_user()
        user.set_password("Old password")
        user.set_password("New password")
        self.assertFalse(user.check_password("Old password"))
        self.assertTrue(user.check_password("New password"))

    def test_invalid_password_does_not_replace_existing_hash(self):
        user = self.new_user()
        user.set_password("Keep this password")
        original_hash = user.password_hash
        for invalid in ("", None, 123, b"bytes"):
            with self.subTest(password_type=type(invalid).__name__):
                with self.assertRaises(ValueError):
                    user.set_password(invalid)
                self.assertEqual(user.password_hash, original_hash)
                self.assertFalse(user.check_password(invalid))

    def test_missing_or_malformed_hash_does_not_authenticate(self):
        user = self.new_user()
        self.assertFalse(user.check_password("anything"))
        for invalid_hash in ("not-a-hash", "unknown$salt$hash"):
            user.password_hash = invalid_hash
            self.assertFalse(user.check_password("anything"))

    def test_persists_existing_fields_with_employee_default(self):
        user = self.new_user()
        # Password whitespace is meaningful and must not be stripped.
        user.set_password("  A password with spaces  ")
        db.session.add(user)
        db.session.commit()
        user_id = user.id
        db.session.remove()
        loaded = db.session.get(User, user_id)
        self.assertEqual(loaded.name, "Test employee")
        self.assertEqual(loaded.address, "1 Test Road")
        self.assertEqual(loaded.role, "EMPLOYEE")
        self.assertTrue(loaded.check_password("  A password with spaces  "))
        self.assertFalse(loaded.check_password("A password with spaces"))
        stored = db.session.execute(text("SELECT password_hash FROM users WHERE id = :id"), {"id": user_id}).scalar_one()
        self.assertNotEqual(stored, "  A password with spaces  ")

    def test_rejects_roles_outside_existing_schema(self):
        user = self.new_user()
        user.set_password("Example password")
        user.role = "SUPERUSER"
        db.session.add(user)
        with self.assertRaises(StatementError):
            db.session.flush()
        db.session.rollback()
