# Installation and Native Builds — v4.0.0

## Python source: Windows, macOS and Linux

Use Python 3.10+ with Tk support. Extract the ZIP, open a terminal in the project folder, and run:

```bash
python hog_desktop.py
```

Windows alternative: `py -3 hog_desktop.py`. Linux may use `python3`. In PyCharm, select a Tk-enabled interpreter and run `hog_desktop.py`. Check Tk with `python -m tkinter`. Source play needs no third-party Python packages. `python hog_ui.py` is the terminal alternative.

The first normal launch opens a welcome tour until it is skipped/completed. Reopen it from Settings. Settings also provides Edit controls and Backup & recovery; Access provides larger text and reduced motion.

## Included Linux native client

Keep the full `native/linux-x86_64/Hog` folder together:

```bash
chmod +x native/linux-x86_64/Hog/Hog
./native/linux-x86_64/Hog/Hog
```

This build was verified on Linux x86-64 with glibc 2.39, Python 3.12.3, Tk 8.6 and PyInstaller 6.22.3. The client does not require a separate Python installation, but still needs a graphical desktop/system graphics libraries. Older glibc compatibility is not claimed; build locally or use source on other systems.

### Per-user installation

The installer requires Python 3 to copy/register the bundled client. It does not install pip packages or use administrator privileges:

```bash
python3 tools/install_linux.py
```

It installs the complete client under `~/.local/lib/hog`, a launcher at `~/.local/bin/hog`, and an application-menu entry at `~/.local/share/applications/hog.desktop`. Open Hog in your desktop menu or run the full launcher path. `hog` also works if `~/.local/bin` is on your PATH. Desktop menu refresh behavior depends on your desktop environment.

For an isolated prefix, use `--prefix /path/to/prefix`. The installer refuses a foreign destination, keeps the native folder together and updates an installation marked as its own.

Uninstall using the same project/installer:

```bash
python3 tools/install_linux.py --uninstall
```

Use the same `--prefix` when uninstalling a custom location. User game data and backups remain outside the installation folder and are preserved.

## Build a native client on the current OS

```bash
python -m pip install -r requirements-build.txt
python tools/build_desktop.py
```

Output is `dist/Hog` on Windows/Linux and includes a `dist/Hog.app` bundle on macOS. Keep complete native output, including `_internal`. Native packages must be built on the target OS; PyInstaller is not a cross-compiler. Some Linux distributions package the Python shared library separately. `build-native.sh` is a convenience wrapper for Unix systems with pip.

Build guidance follows the [PyInstaller manual](https://www.pyinstaller.org/en/stable/). Build requirements are optional and pinned; they are not needed for source play.

## Windows installer recipe

On Windows with Python/Tk installed:

1. Run `build-windows.bat`, or the build commands above.
2. Install Inno Setup on that build machine.
3. Compile the recipe:

```powershell
ISCC.exe installers\windows\Hog.iss
```

If ISCC is not on PATH, use its installed full path. The recipe expects `dist/Hog` and writes `dist-installers/Hog-v4.0.0-windows-setup.exe`. It installs for the current user, offers a desktop shortcut and registers an uninstaller. It does not include rules that remove AppData progress. The recipe is unsigned. See the [official Inno Setup compiler reference](https://jrsoftware.org/ishelp/topic_compilercmdline.htm).

**No Windows executable or installer was built/run in this Linux environment.** Test on Windows before attaching one to a release.

## macOS disk-image recipe

On macOS, build the native app, then run:

```bash
python tools/build_macos_dmg.py
```

The builder uses `ditto` to preserve bundle symlinks and `hdiutil` to make `dist-installers/Hog-v4.0.0-macos.dmg`, containing Hog.app and an Applications shortcut. This follows [Apple's disk-image packaging guidance](https://developer.apple.com/documentation/xcode/packaging-mac-software-for-distribution). The result is a drag-to-Applications package, not a signed/notarized distribution. Signing/notarization are not configured and require your own Apple release process.

**No macOS bundle or disk image was built/run here.** Test on the target macOS version/architecture before publishing it.

## Manual GitHub build workflow

`.github/workflows/native-builds.yml` provides manual Linux/Windows/macOS jobs with tests, network checks, builds and native smoke launches. It creates review artifacts; it does not publish releases. It was supplied as source and has not run in your GitHub account. Check all job logs and test output/installers on target systems. See [docs/PUBLISHING.md](docs/PUBLISHING.md).

## Data and compatibility

Settings/database paths remain per-user. Schema 1 and 2 databases receive a matching pre-upgrade backup before migration to schema 3; existing backup files are not overwritten. Manual saved-match JSON remains schema 1. Older settings load with default action keys and welcome status. Earlier releases reject schema 3; use the matching old database backup when downgrading.

Use Settings > Backup & recovery for portable export/import. Restore validates in isolation and creates a current-data safety export before replacing data. It does not merge. See [RECOVERY.md](RECOVERY.md) for data locations and undo steps.

## Checks and display

`--version` needs no display. `--smoke-test` briefly opens a desktop using temporary data. Run the suite with:

```bash
python -m unittest discover -s tests -v
python -m doctest hog.py dice.py
python tools/network_smoke.py
```

GUI classes skip when no display is available. The standard-text main window minimum is 960 × 720. Below 1180 wide, dashboard navigation uses two rows and the match journal initially hides. Larger text can need a larger window.

## Private multiplayer

Run `python hog_server.py` in a separate process, then open Online in the desktop. Default local endpoint: `http://127.0.0.1:8765`. Both players need the same reachable relay and room code. The native package is a client; no public server is deployed. See [ONLINE.md](ONLINE.md) for LAN/HTTPS and reconnect details.
