"""Opponent Scout Flask app.

gunicorn starts the app by calling create_app() (see the Dockerfile).
"""

from flask import Flask, jsonify, render_template, request
from pymongo.errors import PyMongoError

from app.db import ensure_user_indexes
from app.routes.games import games_bp
from app.routes.health import health_bp
from app.routes.onepager import onepager_bp
from app.routes.players import players_bp
from app.routes.refresh import refresh_bp
from app.routes.saved import saved_bp
from app.routes.teams import teams_bp


def create_app():
    app = Flask(__name__)
    # Re-read HTML templates when they change. gunicorn's --reload only
    # watches Python files, so without this, template edits need a restart.
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.register_blueprint(health_bp)
    app.register_blueprint(teams_bp)
    app.register_blueprint(games_bp)
    app.register_blueprint(players_bp)
    app.register_blueprint(saved_bp)
    app.register_blueprint(refresh_bp)
    app.register_blueprint(onepager_bp)

    try:
        ensure_user_indexes()
    except PyMongoError:
        pass  # The database is down; the health check reports it, indexes come next start.

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/scout")
    def scout():
        return render_template("scout.html")

    @app.get("/team/<abbreviation>")
    def team_page(abbreviation):
        return render_template("team.html")

    @app.get("/player/<player_id>")
    def player_page(player_id):
        return render_template("player.html")

    @app.get("/onepager/<player_id>")
    def onepager_page(player_id):
        return render_template("onepager.html")

    @app.get("/onepagers")
    def onepagers_page():
        return render_template("onepagers.html")

    @app.get("/reports")
    def reports_page():
        return render_template("reports.html")

    @app.get("/reports/<report_id>")
    def report_page(report_id):
        return render_template("report.html")

    @app.get("/game/<game_id>")
    def game_page(game_id):
        return render_template("game.html")

    @app.errorhandler(PyMongoError)
    def database_down(_err):
        return jsonify({"error": "The database is not answering. Try again in a moment."}), 503

    @app.errorhandler(404)
    def not_found(err):
        if request.path.startswith("/api/"):
            return jsonify({"error": "There is no API endpoint at this address."}), 404
        return err

    return app
