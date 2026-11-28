import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template

from backend.database import database_url, db
from backend.routes.maps import maps_api


def create_app(config=None):
    root = Path(__file__).resolve().parent.parent
    load_dotenv(root / ".env.local")
    load_dotenv(root / ".env")
    app = Flask(__name__)
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI=database_url(),
        SECRET_KEY=os.getenv("SECRET_KEY"),
        GOOGLE_MAPS_API_KEY=os.getenv("GOOGLE_MAPS_API_KEY", ""),
        GOOGLE_MAPS_BROWSER_API_KEY=os.getenv("GOOGLE_MAPS_BROWSER_API_KEY", ""),
    )
    app.config.update(config or {})
    db.init_app(app)
    app.register_blueprint(maps_api)

    @app.get("/")
    def dashboard():
        return render_template("dashboard.html")

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
