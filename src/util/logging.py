import os.path
import os
import logging


def _decorated_open(fn):
    def new_open(self):
        os.makedirs(os.path.dirname(self.baseFilename), exist_ok=True)
        return fn(self)
    return new_open


def fix_add_parent_mkdir_on_log_write():
    """Makes every FileHandler create the parent directories before they start writing"""
    logging.FileHandler._open = _decorated_open(logging.FileHandler._open)

