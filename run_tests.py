#!/usr/bin/python3
import subprocess
from pathlib import Path

wd = Path(__file__).parent / "src"

if __name__ == "__main__":
    subprocess.call(["python3", "-m", "test.runner"], cwd=str(wd))
