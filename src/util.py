from datetime import datetime

date_format = '%Y-%m-%dT%H:%M:%S.%fZ'


def parse_date(s: str) -> datetime:
    """Parses the datetime following a simplified ISO-8601 standard"""
    if isinstance(s, datetime):
        return s
    return datetime.strptime(s, date_format)


def clean_dict(d: dict):
    """Removes entries with null value from dictionaries"""
    return {key: val for (key, val) in d.items() if val is not None}

