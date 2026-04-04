"""
Simple Flask web adapter that uses the core service.
Much cleaner than the original - just routes that delegate to the service.
"""

import threading
import time
import re
from flask import Flask, render_template, redirect, url_for, request, abort
from ...core.models import create_database
from ...core.service import TestReportService

def create_app(config: dict = None):
    """Create Flask app - much simpler than before."""
    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')

    config = config or {}
    app.config.update(config)

    # Simple database setup
    engine, SessionLocal = create_database()

    def get_service():
        """Get a service instance with a fresh session."""
        session = SessionLocal()
        return TestReportService(session), session

    # Setup projects from config
    def setup_projects():
        service, session = get_service()
        try:
            for proj_cfg in config.get("projects", []):
                if not proj_cfg.get("enabled", True):
                    continue
                name = proj_cfg["name"]
                identifier = proj_cfg.get("identifier")
                out_dir = proj_cfg["out_dir"]
                service.create_or_update_project(name, identifier, out_dir)
        finally:
            session.close()

    setup_projects()

    # Template filter
    @app.template_filter("to_path")
    def to_path_filter(name: str) -> str:
        if not name:
            return "/"
        p = "/" + name.replace(".", "/")
        return re.sub(r"/{2,}", "/", p)

    # Context processor for project list
    @app.context_processor
    def inject_projects():
        service, session = get_service()
        try:
            order = request.args.get("order", "name")
            project_data = service.get_project_list_with_stats(order)
            return {
                "project_list": project_data["projects"],
                "order_mode": project_data["order_mode"]
            }
        finally:
            session.close()

    # Routes
    @app.route("/")
    def index():
        service, session = get_service()
        try:
            default_project = service.choose_default_project(config)
            if default_project:
                return redirect(url_for("summary", project_id=default_project.id))
            return render_template("base.html", content="No projects configured.")
        finally:
            session.close()

    @app.route("/projects/<int:project_id>/summary/", defaults={"subpath": ""})
    @app.route("/projects/<int:project_id>/summary/<path:subpath>")
    def summary(project_id, subpath):
        service, session = get_service()
        try:
            # Parse filters
            f_types = request.args.getlist("f_type")
            f_regexes = request.args.getlist("f_regex")
            filters = []
            for f_type, f_regex in zip(f_types, f_regexes):
                f_type = f_type.strip().lower()
                f_regex = f_regex.strip()
                if f_type not in ("include", "exclude") or not f_regex:
                    continue
                try:
                    re.compile(f_regex)
                except re.error:
                    continue
                filters.append((f_type, f_regex))

            trim = request.args.get("trim", "0") in ("1", "true", "yes")
            summary_runs = config.get("summary_runs", 10)

            data = service.get_project_summary(
                project_id=project_id,
                subpath=subpath,
                summary_runs=summary_runs,
                filters=filters,
                trim=trim
            )
            return render_template("summary.html", **data)

        except ValueError:
            abort(404)
        finally:
            session.close()

    @app.route("/projects/<int:project_id>/runs/<int:run_id>")
    def testrun_view(project_id, run_id):
        service, session = get_service()
        try:
            data = service.get_test_run_details(project_id, run_id)
            return render_template("testrun.html", **data)
        except ValueError:
            abort(404)
        finally:
            session.close()

    @app.route("/projects/<int:project_id>/tests/<int:test_id>")
    def test_view(project_id, test_id):
        service, session = get_service()
        try:
            data = service.get_test_details(project_id, test_id)
            return render_template("test.html", **data)
        except ValueError:
            abort(404)
        finally:
            session.close()

    @app.route("/projects/<int:project_id>/delete", methods=["POST"])
    def delete_project(project_id):
        service, session = get_service()
        try:
            service.delete_project(project_id)
            # Redirect to a remaining project
            default_project = service.choose_default_project(config)
            if default_project:
                return redirect(url_for("summary", project_id=default_project.id))
            return redirect(url_for("index"))
        finally:
            session.close()

    # API routes
    @app.get("/api/projects/by-identifier/<string:identifier>")
    def api_project_by_identifier(identifier):
        service, session = get_service()
        try:
            project = service.get_project_by_identifier(identifier)
            if not project:
                abort(404)
            return {
                "id": project.id,
                "identifier": project.identifier,
                "name": project.name
            }
        finally:
            session.close()

    @app.get("/p/<string:identifier>")
    def go_by_identifier(identifier):
        service, session = get_service()
        try:
            project = service.get_project_by_identifier(identifier)
            if not project:
                abort(404)
            return redirect(url_for("summary", project_id=project.id))
        finally:
            session.close()

    # Background scanner - simple and straightforward
    def scanner_loop():
        with app.app_context():
            while True:
                try:
                    service, session = get_service()
                    try:
                        processed = service.scan_and_parse_new_files()
                        if processed:
                            print(f"[SCANNER] Processed {len(processed)} new files")
                    finally:
                        session.close()
                except Exception as e:
                    print(f"[SCANNER] Error: {e}")
                time.sleep(config.get("scan_interval", 10))

    scanner_thread = threading.Thread(target=scanner_loop, daemon=True)
    scanner_thread.start()

    return app
