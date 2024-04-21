from contextlib import contextmanager
from typing import Iterator, cast

import django
import pytest
from _pytest.fixtures import SubRequest
from django.core.management import call_command as django_command
from esdbclient import EventStoreDBClient, StreamState
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from event_sourcery.event_store import BackendFactory, InMemoryBackendFactory
from event_sourcery_django import DjangoBackendFactory
from event_sourcery_esdb import ESDBBackendFactory
from event_sourcery_sqlalchemy import SQLAlchemyBackendFactory
from tests.conftest import DeclarativeBase
from tests.mark import xfail_if_not_implemented_yet


@contextmanager
def sql_session(
    url: str,
    declarative_base: DeclarativeBase,
) -> Iterator[Session]:
    engine = create_engine(url, future=True)
    try:
        declarative_base.metadata.create_all(bind=engine)
    except OperationalError:
        pytest.skip(f"{engine.url.drivername} test database not available, skipping")
    else:
        with Session(bind=engine) as session:
            yield session

        declarative_base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def sqlite_session(
    request: pytest.FixtureRequest, declarative_base: DeclarativeBase
) -> Iterator[Session]:
    xfail_if_not_implemented_yet(request, "sqlite")
    with sql_session("sqlite:///:memory:", declarative_base) as session:
        yield session


@pytest.fixture()
def sqlite_factory(
    sqlite_session: Session,
) -> SQLAlchemyBackendFactory:
    return SQLAlchemyBackendFactory(sqlite_session)


@pytest.fixture()
def postgres_session(
    request: pytest.FixtureRequest, declarative_base: DeclarativeBase
) -> Iterator[Session]:
    xfail_if_not_implemented_yet(request, "postgres")
    url = "postgresql://es:es@localhost:5432/es"
    with sql_session(url, declarative_base) as session:
        yield session


@pytest.fixture()
def postgres_factory(
    postgres_session: Session,
) -> SQLAlchemyBackendFactory:
    return SQLAlchemyBackendFactory(postgres_session)


@pytest.fixture()
def esdb() -> Iterator[EventStoreDBClient]:
    client = EventStoreDBClient(uri="esdb://localhost:2113?Tls=false")
    commit_position = client.get_commit_position()
    yield client
    for event in client._connection.streams.read(commit_position=commit_position):
        if not event.stream_name.startswith("$"):
            client.delete_stream(
                event.stream_name,
                current_version=StreamState.ANY,
            )
    for sub in client.list_subscriptions():
        client.delete_subscription(sub.group_name)


@pytest.fixture()
def esdb_factory(
    request: pytest.FixtureRequest,
    esdb: EventStoreDBClient,
) -> ESDBBackendFactory:
    skip_esdb = request.node.get_closest_marker("skip_esdb")
    if skip_esdb:
        reason = skip_esdb.kwargs.get("reason", "")
        pytest.skip(f"Skipping ESDB tests: {reason}")

    xfail_if_not_implemented_yet(request, "esdb")
    return ESDBBackendFactory(esdb)


@pytest.fixture()
def in_memory_factory(request: pytest.FixtureRequest) -> BackendFactory:
    skip_in_memory = request.node.get_closest_marker("skip_in_memory")
    if skip_in_memory:
        reason = skip_in_memory.kwargs.get("reason", "")
        pytest.skip(f"Skipping InMemory tests: {reason}")

    xfail_if_not_implemented_yet(request, "in_memory")
    return InMemoryBackendFactory()


@pytest.fixture()
def django_factory(transactional_db: None, request: SubRequest) -> DjangoBackendFactory:
    django.setup()
    django_command("migrate")
    skip_django = request.node.get_closest_marker("skip_django")
    if skip_django:
        reason = skip_django.kwargs.get("reason", "")
        pytest.skip(f"Skipping Django tests: {reason}")

    xfail_if_not_implemented_yet(request, "django")
    return DjangoBackendFactory()


@pytest.fixture(
    params=[
        "in_memory_factory",
        "esdb_factory",
        "sqlite_factory",
        "postgres_factory",
        "django_factory",
    ]
)
def event_store_factory(request: SubRequest) -> BackendFactory:
    return cast(BackendFactory, request.getfixturevalue(request.param))
