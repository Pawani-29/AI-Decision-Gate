from flask import Blueprint, render_template

main_bp = Blueprint("main", __name__)


@main_bp.get("/")
def home():
    """Render the MVP landing page."""
    return render_template("index.html")
