"""Build a native one-folder desktop package on the target operating system.

Install build dependencies first: python -m pip install -r requirements-build.txt
This tool is optional; source play requires only Python and Tkinter.
"""

import argparse
from pathlib import Path
import subprocess
import sys


def build_command(python=sys.executable, destination=None):
    root = Path(__file__).resolve().parents[1]
    destination = Path(destination).resolve() if destination else root / "dist"
    return [python, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--windowed",
            "--name", "Hog", "--distpath", str(destination),
            "--workpath", str(root / "build"), "--specpath", str(root / "build"),
            "--add-data", f"{root / 'assets/sounds'}:assets/sounds",
            str(root / "hog_desktop.py")]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default=sys.executable, help="Python interpreter with Tk and PyInstaller")
    parser.add_argument("--destination", help="native output folder")
    args = parser.parse_args()
    subprocess.run(build_command(args.python, args.destination), check=True)


if __name__ == "__main__":
    main()
