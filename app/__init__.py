from typing import Mapping

from dotenv import load_dotenv
from flask import Flask
from pathlib import Path


def create_app(test_config: Mapping[str, object] | None = None) -> Flask:
    """Create the application using the minimal MVP configuration."""
    load_dotenv()
    app = Flask(__name__)
    app.config.from_mapping(
        UPLOAD_FOLDER=Path(app.root_path).parent / "uploads",
    )
    if test_config:
        app.config.update(test_config)

    from app.routes.main import main_bp

    app.register_blueprint(main_bp)
    return app
