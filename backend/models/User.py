from werkzeug.security import check_password_hash, generate_password_hash

from backend.database import db


class User(db.Model):
    """Map the existing users table; passwords are set through set_password."""

    __tablename__ = "users"

    id = db.Column(
        db.BigInteger().with_variant(db.Integer, "sqlite"),
        db.Identity(),
        primary_key=True,
    )
    name = db.Column(db.Text, nullable=False)
    address = db.Column(db.Text, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    role = db.Column(
        db.Enum(
            "EMPLOYEE", "ADMIN", name="user_role",
            validate_strings=True, create_constraint=True,
        ),
        nullable=False,
        default="EMPLOYEE",
    )

    def set_password(self, password):
        """Hash a password without keeping its plaintext on the model."""
        if not isinstance(password, str) or not password:
            raise ValueError("Password must be a non-empty string.")
        self.password_hash = generate_password_hash(password, method="scrypt")

    def check_password(self, password):
        """Return False for an incorrect password or an unusable stored hash."""
        if not isinstance(password, str) or not password or not self.password_hash:
            return False
        try:
            return check_password_hash(self.password_hash, password)
        except (ValueError, TypeError):
            return False
