import base64
import threading
import uuid
from dataclasses import dataclass, field

import duckdb

from local_bigquery.engine import database
from local_bigquery.errors import BigQueryError


@dataclass
class Session:
    id: str
    project_id: str
    cursor: duckdb.DuckDBPyConnection
    lock: threading.Lock = field(default_factory=threading.Lock)
    variables: dict = field(default_factory=dict)
    settings: dict = field(default_factory=dict)


_sessions: dict[str, Session] = {}


def create(project_id: str) -> Session:
    session_id = base64.urlsafe_b64encode(uuid.uuid4().bytes).decode().rstrip("=")
    session = Session(session_id, project_id, database.connection().cursor())
    _sessions[session_id] = session
    return session


def get(session_id: str) -> Session:
    if session_id not in _sessions:
        raise BigQueryError("invalid", "Invalid input session id.")
    return _sessions[session_id]


def abort(session_id: str):
    if session := _sessions.pop(session_id, None):
        session.cursor.close()
