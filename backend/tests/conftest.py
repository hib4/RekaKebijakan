import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


@pytest.fixture(scope="session")
def database_url() -> str:
    application_url = make_url(
        os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://rekakebijakan:rekakebijakan@localhost:5432/rekakebijakan",
        )
    )
    test_url = make_url(os.getenv("TEST_DATABASE_URL")) if os.getenv("TEST_DATABASE_URL") else application_url.set(
        database=f"{application_url.database}_test"
    )
    database_name = test_url.database
    if not database_name or not database_name.replace("_", "").isalnum():
        raise ValueError("Test database name may only contain letters, numbers, and underscores")

    admin_engine = create_engine(application_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as connection:
        exists = connection.execute(
            text("SELECT 1 FROM pg_database WHERE datname=:name"), {"name": database_name}
        ).scalar_one_or_none()
        if not exists:
            connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')
    admin_engine.dispose()
    return test_url.render_as_string(hide_password=False)


@pytest.fixture(autouse=True)
def clean_database(database_url: str):
    root = Path(__file__).resolve().parent.parent
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE citations, document_chunks, jobs, documents, sessions, simulations, users CASCADE"))
    engine.dispose()
    yield
