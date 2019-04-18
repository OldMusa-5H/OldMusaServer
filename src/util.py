import time
from datetime import datetime
import sqlite3

from sqlalchemy.engine import Engine
from sqlalchemy import event

date_format = '%Y-%m-%dT%H:%M:%S.%fZ'


def parse_date(s: str) -> datetime:
    """Parses the datetime following a simplified ISO-8601 standard"""
    if isinstance(s, datetime):
        return s
    return datetime.strptime(s, date_format)


def clean_dict(d: dict):
    """Removes entries with null value from dictionaries"""
    return {key: val for (key, val) in d.items() if val is not None}


def get_unix_time() -> int:
    return int(time.time())


def install_sqlite3_foreign_fix():
    @event.listens_for(Engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        if type(dbapi_connection) is sqlite3.Connection:  # play well with other DB backends
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()