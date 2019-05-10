import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime
from typing import List

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event, Column, String
from sqlalchemy.engine import Engine

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


def fix_db_string_collation(db: SQLAlchemy):
    for t in iter(db.Model.metadata.tables.values()):
        bind = t.info.get('bind_key')
        engine = db.get_engine(bind=bind)

        cols = t.columns  # type: List[Column]

        for col in cols:
            if type(col.type) != String:
                continue
            t = col.type  # type: String
            t.collation = get_actual_collation(t.collation, engine.name)


def get_actual_collation(collation, engine):
    translation_table = {
        "mysql": {
            "utf8_binary": "utf8_bin"
        },
        "sqlite": {
            "utf8_binary": None  # Can't find replacement
        }
    }
    if engine not in translation_table: return collation

    collation_table = translation_table[engine]
    if collation not in collation_table: return collation

    return collation_table[collation]
