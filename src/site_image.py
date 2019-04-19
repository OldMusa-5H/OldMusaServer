import os
from pathlib import Path
from typing import Optional

basedir = Path("./image")


def get_image(site_id: int) -> Optional[Path]:
    path = basedir / str(site_id)  # type: Path
    if path.is_file():
        return path
    return None


def set_image(site_id: int, data: bytes):
    path = (basedir / str(site_id))
    if not path.parent.is_dir():
        path.parent.mkdir(parents=True)
    path.write_bytes(data)


def delete_image(site_id: int) -> bool:
    path = basedir / str(site_id)
    if path.is_file():
        os.remove(path)
        return True
    return False


def set_storage_dir(dir: str):
    global basedir
    basedir = Path(dir)

