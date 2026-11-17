"""Opponent Scout Flask app.

gunicorn starts the app by calling create_app() (see the Dockerfile).
"""

from flask import Flask, render_template

from app.routes.health import health_bp


def create_app():
    app = Flask(__name__)
    app.register_blueprint(health_bp)

    @app.get("/")
    def index():
        return render_template("index.html")

    return app
