from flask import Flask
from pathlib import Path


def create_app() -> Flask:
    """Create the application using the minimal MVP configuration."""
    app = Flask(__name__)
    app.config.from_mapping(
        UPLOAD_FOLDER=Path(app.root_path).parent / "uploads",
    )

    from app.routes.main import main_bp

    app.register_blueprint(main_bp)
    return app
