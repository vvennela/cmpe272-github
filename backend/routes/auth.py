"""Employee signup, login and logout using signed Flask sessions."""
import hmac
import secrets

from email_validator import EmailNotValidError, validate_email
from flask import (
    Blueprint, current_app, g, jsonify, redirect, render_template, request,
    session, url_for,
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.security import check_password_hash, generate_password_hash

from backend.database import db
from backend.models import User


auth = Blueprint("auth", __name__)
limiter = Limiter(key_func=get_remote_address, default_limits=[])
# Equal-cost password verification for an unknown email.
DUMMY_HASH = generate_password_hash(secrets.token_urlsafe(32), method="scrypt")


def csrf_token():
    if not current_app.secret_key:
        return ""
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def wants_json():
    return request.accept_mimetypes.best == "application/json"


def account_page(mode, errors=None, message=None, status=200):
    errors = errors or {}
    if request.method == "POST" and wants_json():
        return jsonify(error=message or "Check the highlighted fields.", errors=errors), status
    values = {key: request.form.get(key, "")[:limit] for key, limit in
              (("name", 100), ("email", 254), ("address", 500))}
    return render_template("account.html", mode=mode, errors=errors,
                           message=message, values=values), status


def signed_in(user):
    session.clear()
    session["user_id"] = user.id
    session.permanent = True
    csrf_token()
    if wants_json():
        return jsonify(redirect=url_for("dashboard"))
    return redirect(url_for("dashboard"), code=303)


@auth.before_app_request
def load_user():
    g.user = None
    # APIs that don't use identity shouldn't require an account-table query.
    user_id = session.get("user_id")
    if user_id is not None and not request.path.startswith(("/static/", "/api/map/")):
        try:
            if type(user_id) is int:
                g.user = db.session.get(User, user_id)
            if g.user is None:
                session.clear()
        except SQLAlchemyError:
            db.session.rollback()
            # Keep the session for a retry; never log account data or credentials.
            g.account_unavailable = True


@auth.app_context_processor
def account_context():
    return {"current_user": getattr(g, "user", None), "csrf_token": csrf_token}


@auth.before_request
def protect_account_requests():
    if not current_app.secret_key:
        return account_page("login", message="Accounts are unavailable. Configure the server session key and try again.", status=503)
    if request.method == "POST":
        request.max_content_length = 16384
        supplied = request.form.get("csrf_token", "")
        expected = session.get("csrf_token", "")
        if not expected or not hmac.compare_digest(supplied.encode(), expected.encode()):
            mode = "signup" if request.endpoint == "auth.signup" else "login"
            return account_page(mode, message="Your session expired. Reload this page and try again.", status=403)


@auth.errorhandler(SQLAlchemyError)
def account_database_error(error):
    db.session.rollback()
    current_app.logger.error("Account database unavailable (%s)", type(error).__name__)
    mode = "signup" if request.endpoint == "auth.signup" else "login"
    return account_page(mode, message="Accounts are temporarily unavailable. Try again shortly.", status=503)


@auth.errorhandler(413)
def body_too_large(error):
    if wants_json():
        return jsonify(error="The form is too large. Shorten your entries and try again.", errors={}), 413
    return render_template("account.html", mode="login", errors={}, values={}, message="The form is too large. Shorten your entries and try again."), 413


@auth.errorhandler(429)
def too_many_requests(error):
    mode = "signup" if request.endpoint == "auth.signup" else "login"
    response = account_page(mode, message="Too many attempts. Wait a minute, then try again.", status=429)
    return response


@auth.after_request
def no_account_cache(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@auth.route("/signup", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def signup():
    if g.user:
        return redirect(url_for("dashboard"))
    if request.method == "GET":
        return account_page("signup")
    errors = {}
    name = request.form.get("name", "").strip()
    address = request.form.get("address", "").strip()
    if not name or len(name) > 100:
        errors["name"] = "Enter your name using 100 characters or fewer."
    if not address or len(address) > 500:
        errors["address"] = "Enter your address using 500 characters or fewer."
    try:
        email = normalize_email(request.form.get("email", ""))
    except ValueError:
        email = None
        errors["email"] = "Enter a valid email address."
    password = request.form.get("password", "")
    if not 15 <= len(password) <= 128:
        errors["password"] = "Use a password between 15 and 128 characters."
    if password != request.form.get("confirm_password", ""):
        errors["confirm_password"] = "The passwords must match."
    if errors:
        return account_page("signup", errors=errors, status=400)
    user = User(name=name, address=address, email=email, role="EMPLOYEE")
    user.set_password(password)
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return account_page("signup", errors={"email": "This email cannot be registered. Try logging in instead."}, status=409)
    return signed_in(user)


def normalize_email(value):
    if not value or len(value) > 254:
        raise ValueError("Invalid email")
    try:
        result = validate_email(value.strip(), check_deliverability=False, allow_smtputf8=False)
        return result.ascii_email.lower()
    except EmailNotValidError as error:
        raise ValueError("Invalid email") from error


@auth.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def login():
    if g.user:
        return redirect(url_for("dashboard"))
    if request.method == "GET":
        return account_page("login")
    password = request.form.get("password", "")
    try:
        email = normalize_email(request.form.get("email", ""))
    except ValueError:
        email = None
    user = db.session.execute(db.select(User).filter_by(email=email)).scalar_one_or_none() if email else None
    if not password or len(password) > 128:
        valid = False
    elif user:
        valid = user.check_password(password)
    else:
        check_password_hash(DUMMY_HASH, password)
        valid = False
    if not valid:
        return account_page("login", message="Email or password is incorrect.", status=401)
    return signed_in(user)


@auth.post("/logout")
def logout():
    session.clear()
    if wants_json():
        return jsonify(redirect=url_for("dashboard"))
    return redirect(url_for("dashboard"), code=303)
