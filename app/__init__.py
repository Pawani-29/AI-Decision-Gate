from flask import Flask


def create_app() -> Flask:
    """Create the application using the minimal MVP configuration."""
    app = Flask(__name__)

    from app.routes.main import main_bp

    app.register_blueprint(main_bp)
    return app
