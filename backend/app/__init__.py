from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_cors import CORS
from pydantic import ValidationError

from .api import api
from .repository import Repository
from .service import WorkflowService


def create_app(config: dict | None = None) -> Flask:
    load_dotenv()
    app = Flask(__name__)
    root = Path(__file__).resolve().parent.parent
    data_dir = Path(os.getenv("DATA_DIR", root / "data"))
    app.config.from_mapping(
        DATABASE_PATH=os.getenv("DATABASE_PATH", data_dir / "rekakebijakan.sqlite3"),
        UPLOAD_DIR=data_dir / "uploads",
        MAX_CONTENT_LENGTH=int(os.getenv("MAX_UPLOAD_BYTES", 16 * 1024 * 1024)),
        JOB_DELAY=float(os.getenv("JOB_DELAY", "0.08")),
        TESTING=False,
    )
    if config:
        app.config.update(config)
    Path(app.config["UPLOAD_DIR"]).mkdir(parents=True, exist_ok=True)
    repository = Repository(str(app.config["DATABASE_PATH"]))
    service = WorkflowService(repository, Path(app.config["UPLOAD_DIR"]), float(app.config["JOB_DELAY"]))
    app.extensions["repository"] = repository
    app.extensions["workflow"] = service
    CORS(app, origins=os.getenv("CORS_ORIGINS", "*"))
    app.register_blueprint(api)

    @app.get("/health")
    def health():
        return jsonify(status="ok", service="rekakebijakan", engine="deterministic-demo")

    @app.errorhandler(ValidationError)
    def validation_error(error):
        details = error.errors(include_url=False)
        return jsonify(error={"code": "validation_error", "message": "Input tidak valid", "details": details}, message="Input tidak valid"), 422

    @app.errorhandler(404)
    def not_found(_error):
        message = "Sumber daya tidak ditemukan"
        return jsonify(error={"code": "not_found", "message": message}, message=message), 404

    @app.errorhandler(413)
    def too_large(_error):
        message = "Berkas terlalu besar"
        return jsonify(error={"code": "payload_too_large", "message": message}, message=message), 413

    @app.errorhandler(Exception)
    def unexpected(error):
        app.logger.exception("Unhandled API error")
        message = "Terjadi kesalahan internal"
        return jsonify(error={"code": "internal_error", "message": message}, message=message), 500

    service.recover()
    return app
