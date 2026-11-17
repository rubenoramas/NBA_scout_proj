"""Opponent Scout Flask app.

gunicorn starts the app by calling create_app() (see the Dockerfile).
"""

from flask import Flask, jsonify, render_template, request
from pymongo.errors import PyMongoError

from app.routes.games import games_bp
from app.routes.health import health_bp
from app.routes.teams import teams_bp


def create_app():
    app = Flask(__name__)
    # Re-read HTML templates when they change. gunicorn's --reload only
    # watches Python files, so without this, template edits need a restart.
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.register_blueprint(health_bp)
    app.register_blueprint(teams_bp)
    app.register_blueprint(games_bp)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/scout")
    def scout():
        return render_template("scout.html")

    @app.errorhandler(PyMongoError)
    def database_down(_err):
        return jsonify({"error": "The database is not answering. Try again in a moment."}), 503

    @app.errorhandler(404)
    def not_found(err):
        if request.path.startswith("/api/"):
            return jsonify({"error": "There is no API endpoint at this address."}), 404
        return err

    return app
