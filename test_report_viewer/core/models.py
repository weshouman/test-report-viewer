from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, DateTime, Float, Text, Boolean, ForeignKey, UniqueConstraint, Index, Enum as SAEnum, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

Base = declarative_base()

class Status(Enum):
    passed = "passed"
    failed = "failed"
    error = "error"
    skipped = "skipped"

class Project(Base):
    __tablename__ = 'project'

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    identifier = Column(String(200), unique=True, nullable=False)
    out_dir = Column(String(1024), nullable=False)

    runs = relationship("TestRun", back_populates="project", cascade="all, delete-orphan")
    tests = relationship("Test", back_populates="project", cascade="all, delete-orphan")

class TestRun(Base):
    __tablename__ = 'test_run'

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("project.id"), nullable=False)
    run_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    filename = Column(String(1024), nullable=False, unique=True)
    total = Column(Integer, default=0)
    failures = Column(Integer, default=0)
    errors = Column(Integer, default=0)
    skipped = Column(Integer, default=0)

    project = relationship("Project", back_populates="runs")
    results = relationship("TestResult", back_populates="testrun", cascade="all, delete-orphan")

class Test(Base):
    __tablename__ = 'test'

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("project.id"), nullable=False)
    name = Column(String(512), nullable=False)
    classname = Column(String(512))

    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_test_name_in_project"),
        Index("ix_test_project_name", "project_id", "name"),
    )

    project = relationship("Project", back_populates="tests")
    results = relationship("TestResult", back_populates="test", cascade="all, delete-orphan")

class TestResult(Base):
    __tablename__ = 'test_result'

    id = Column(Integer, primary_key=True)
    test_id = Column(Integer, ForeignKey("test.id"), nullable=False)
    testrun_id = Column(Integer, ForeignKey("test_run.id"), nullable=False)
    status = Column(SAEnum(Status), nullable=False)
    time = Column(Float, default=0.0)
    message = Column(Text)
    regression = Column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint("test_id", "testrun_id", name="uq_result_test_run"),
    )

    test = relationship("Test", back_populates="results")
    testrun = relationship("TestRun", back_populates="results")

# Simple database setup
def create_database(database_url=None):
    """Create database engine and session factory."""
    import os
    if database_url is None:
        # Default to data directory, create it if it doesn't exist
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
        os.makedirs(data_dir, exist_ok=True)
        default_db_path = os.path.join(data_dir, "junit_dashboard.db")
        database_url = os.environ.get("DATABASE_URL", f"sqlite:///{default_db_path}")
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal