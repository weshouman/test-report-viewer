"""
Simple CLI adapter that uses the core service.
Much cleaner than complex Click groups - just straightforward commands.
"""

import click
from ...core.models import create_database
from ...core.service import TestReportService

def get_service():
    """Get a service instance."""
    engine, SessionLocal = create_database()
    session = SessionLocal()
    return TestReportService(session), session

@click.group()
def cli():
    """Test Report Viewer CLI - Simple and straightforward."""
    pass

@cli.command()
def scan():
    """Scan for new test files and process them."""
    service, session = get_service()
    try:
        processed = service.scan_and_parse_new_files()

        if not processed:
            click.echo("No new test files found.")
            return

        click.echo(f"Processed {len(processed)} new test files:")
        for file_path in processed:
            click.echo(f"  [OK] {file_path}")

    except Exception as e:
        click.echo(f"Error: {e}")
    finally:
        session.close()

@cli.command("list-projects")
def list_projects():
    """List all projects with their latest stats."""
    service, session = get_service()
    try:
        data = service.get_project_list_with_stats()
        projects = data["projects"]

        if not projects:
            click.echo("No projects configured.")
            return

        click.echo("Projects:")
        for project, tooltip in projects:
            click.echo(f"  {project.id}: {project.name} ({project.identifier})")
            click.echo(f"       Directory: {project.out_dir}")
            # Parse tooltip for stats
            lines = tooltip.split('\n')
            if len(lines) >= 3:
                click.echo(f"       {lines[2]}")  # "Last: X/Y passed"

    except Exception as e:
        click.echo(f"Error: {e}")
    finally:
        session.close()

@cli.command("add-project")
@click.argument("name")
@click.argument("out_dir")
@click.option("--identifier", help="Project identifier (auto-generated if not provided)")
def add_project(name, out_dir, identifier):
    """Add a new project."""
    service, session = get_service()
    try:
        project = service.create_or_update_project(name, identifier, out_dir)
        click.echo(f"[OK] Created project: {project.name} ({project.identifier})")
        click.echo(f"  ID: {project.id}")
        click.echo(f"  Directory: {project.out_dir}")

    except Exception as e:
        click.echo(f"Error: {e}")
    finally:
        session.close()

@cli.command("project-summary")
@click.argument("project_id", type=int)
@click.option("--runs", default=5, help="Number of recent runs to show")
def project_summary(project_id, runs):
    """Show project summary."""
    service, session = get_service()
    try:
        data = service.get_project_summary(project_id, summary_runs=runs)
        project = data["project"]

        click.echo(f"Project: {project.name} ({project.identifier})")
        click.echo(f"Directory: {project.out_dir}")
        click.echo()

        if not data["runs"]:
            click.echo("No test runs found.")
            return

        latest_counts = data["latest_counts"]
        total = sum(latest_counts.values())

        click.echo(f"Latest run results ({total} tests):")
        for status, count in latest_counts.items():
            if count > 0:
                click.echo(f"  {status.capitalize()}: {count}")

        click.echo(f"\nShowing {len(data['runs'])} most recent runs:")
        for run in reversed(data["runs"]):  # newest first
            click.echo(f"  {run.run_at} - {run.total} tests ({run.failures} failed, {run.errors} errors)")

    except Exception as e:
        click.echo(f"Error: {e}")
    finally:
        session.close()