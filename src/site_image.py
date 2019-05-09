import os
from pathlib import Path
from typing import Optional


class ImageManager:
    def __init__(self, save_dir="./image"):
        self.basedir = Path(save_dir)

    def get_image(self, site_id: int) -> Optional[Path]:
        path = self.basedir / str(site_id)  # type: Path
        if path.is_file():
            return path
        return None

    def set_image(self, site_id: int, data: bytes):
        path = (self.basedir / str(site_id))
        if not path.parent.is_dir():
            path.parent.mkdir(parents=True)
        path.write_bytes(data)

    def delete_image(self, site_id: int) -> bool:
        path = self.basedir / str(site_id)
        if path.is_file():
            os.remove(path)
            return True
        return False

    def set_storage_dir(self, dir: str):
        self.basedir = Path(dir)
