import os
import glob
from .models import Project, TestRun

def scan_projects(session):
    """Scan all projects for new JUnit XML files."""
    projects = session.query(Project).all()
    new_files = []

    for project in projects:
        out_dir = project.out_dir
        if not os.path.isdir(out_dir):
            continue

        pattern = os.path.join(out_dir, "TEST-*.xml")
        files = sorted(glob.glob(pattern))

        for file_path in files:
            abs_path = os.path.abspath(file_path)
            # Skip if already ingested
            exists = session.query(TestRun).filter_by(filename=abs_path).first()
            if not exists:
                new_files.append((project, abs_path))

    return new_files