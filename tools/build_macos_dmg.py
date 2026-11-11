"""Create an unsigned drag-to-Applications disk image on macOS.

Build dist/Hog.app with tools/build_desktop.py first. Signing/notarization
requires the maintainer's Apple credentials and is not performed here.
"""
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from hog import VERSION


def main():
    if sys.platform != 'darwin':
        raise SystemExit('Build this disk image on macOS.')
    app = ROOT / 'dist/Hog.app'
    if not app.is_dir():
        raise SystemExit('Build dist/Hog.app first: python tools/build_desktop.py')
    output = ROOT / 'dist-installers'
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        stage = Path(temporary) / 'Hog'
        stage.mkdir()
        subprocess.run(['ditto', str(app), str(stage / 'Hog.app')], check=True)
        (stage / 'Applications').symlink_to('/Applications')
        subprocess.run(['hdiutil', 'create', '-volname', 'Hog', '-srcfolder', str(stage),
                        '-ov', '-format', 'UDZO', str(output / f'Hog-v{VERSION}-macos.dmg')], check=True)


if __name__ == '__main__': main()
