from pathlib import Path

from flask import Blueprint, current_app, render_template, request

from app.services.payment_request import process_payment_request

main_bp = Blueprint("main", __name__)


@main_bp.get("/")
def home():
    """Render the MVP landing page."""
    return render_template("index.html")


@main_bp.route("/payment-request", methods=["GET", "POST"])
def payment_request():
    """Collect the evidence required for a contractor payment review."""
    if request.method == "POST":
        result = process_payment_request(
            files=request.files,
            payment_amount=request.form.get("payment_amount", ""),
            upload_folder=Path(current_app.config["UPLOAD_FOLDER"]),
        )
        if result.is_valid:
            return render_template(
                "payment_request.html",
                payment_amount=result.payment_amount,
                uploaded_documents=result.uploaded_documents,
            )

        return render_template(
            "payment_request.html",
            errors=result.errors,
            payment_amount=request.form.get("payment_amount", ""),
        ), 400

    return render_template("payment_request.html")
