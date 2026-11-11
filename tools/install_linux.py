"""Install the bundled Linux client for one user; never touch game data.

Run: python3 tools/install_linux.py
Remove: python3 tools/install_linux.py --uninstall
Use --prefix for an isolated installation (default ~/.local).
"""

import argparse
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from hog import VERSION


def locations(prefix):
    prefix = Path(prefix).expanduser().resolve()
    return prefix, prefix / 'lib/hog', prefix / 'bin/hog', prefix / 'share/applications/hog.desktop'


def _owned(folder):
    marker = folder / 'hog-install.json'
    try:
        data = json.loads(marker.read_text())
        return data.get('owner') == 'hog-user-installer' and data.get('schema') == 1
    except (OSError, ValueError, AttributeError):
        return False


def install(prefix, source=None):
    if not sys.platform.startswith('linux') or platform.machine().lower() not in ('x86_64', 'amd64'):
        raise ValueError('This bundled native client requires Linux x86-64.')
    prefix, folder, launcher, desktop = locations(prefix)
    if any(ord(char) < 32 for char in str(prefix)):
        raise ValueError('Installation paths cannot contain control characters.')
    source = Path(source or ROOT / 'native/linux-x86_64/Hog').resolve()
    if not (source / 'Hog').is_file() or not (source / '_internal').is_dir():
        raise ValueError('Keep the complete native/linux-x86_64/Hog folder.')
    if source == folder or folder in source.parents or source in folder.parents:
        raise ValueError('The installation source must be outside the destination.')
    if folder.is_symlink() or launcher.is_symlink() or desktop.is_symlink():
        raise ValueError('Installation destinations cannot be symbolic links.')
    if folder.exists() and not _owned(folder):
        raise ValueError('Destination is not owned by this installer; choose another --prefix.')
    if launcher.exists() and not folder.exists():
        raise ValueError('A different launcher already exists at this prefix.')
    if desktop.exists() and not folder.exists():
        raise ValueError('A different desktop entry already exists at this prefix.')
    folder.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.hog-install-', dir=folder.parent))
    old = None
    try:
        shutil.copytree(source, stage / 'app', symlinks=True)
        (stage / 'app/Hog').chmod(0o755)
        shutil.copy2(ROOT / 'assets/hog-icon.svg', stage / 'app/hog-icon.svg')
        (stage / 'app/hog-install.json').write_text(json.dumps({'owner': 'hog-user-installer', 'schema': 1, 'version': VERSION}))
        if folder.exists():
            old = stage / 'previous'
            folder.rename(old)
        try:
            (stage / 'app').rename(folder)
        except OSError:
            if old: old.rename(folder)
            raise
        launcher.parent.mkdir(parents=True, exist_ok=True)
        desktop.parent.mkdir(parents=True, exist_ok=True)
        launcher.write_text('#!/bin/sh\nexec ' + shlex.quote(str(folder / 'Hog')) + ' "$@"\n')
        launcher.chmod(0o755)
        # Desktop Entry specification quotes (not shell quotes); escape % field codes.
        command = str(launcher).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%')
        icon = str(folder / 'hog-icon.svg')
        desktop.write_text('[Desktop Entry]\nType=Application\nName=Hog\nComment=The dice strategy game\n'
                           f'Exec="{command}"\nIcon={icon}\nTerminal=false\nCategories=Game;BoardGame;\n')
        return launcher
    finally:
        shutil.rmtree(stage)


def uninstall(prefix):
    prefix, folder, launcher, desktop = locations(prefix)
    if not _owned(folder):
        raise ValueError('No owned Hog installation was found at this prefix.')
    for path in (launcher, desktop):
        if path.exists() or path.is_symlink(): path.unlink()
    shutil.rmtree(folder)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prefix', default=str(Path.home() / '.local'))
    parser.add_argument('--source', help='native one-folder build, primarily for maintainers')
    parser.add_argument('--uninstall', action='store_true')
    args = parser.parse_args()
    try:
        if args.uninstall:
            uninstall(args.prefix)
            print('Hog uninstalled. Local progress and backups were preserved.')
        else:
            print(f'Hog installed: {install(args.prefix, args.source)}')
            print('Open Hog from your application menu or run that launcher path.')
        return 0
    except (OSError, ValueError) as error:
        print(f'Installation failed: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
