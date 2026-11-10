# Installation and Native Builds

## Source / Windows, macOS, Linux

Install Python 3.10+ with Tk support. Extract the project folder and run:

```bash
python hog_desktop.py
```

Windows alternative: `py -3 hog_desktop.py`. Linux may use `python3`. Run `python -m tkinter` to check Tk. Source play uses no third-party Python packages. A terminal-only alternative is `python hog_ui.py`.

## Included Linux Package

Keep the full `native/linux-x86_64/Hog` folder together. Run `chmod +x native/linux-x86_64/Hog/Hog`, then `./native/linux-x86_64/Hog/Hog`. This build was verified on x86_64 Linux with glibc 2.39 and a virtual graphical display. Older glibc systems may need a local build or source play. It is not a Windows executable.

## Build for Windows

On Windows, install Python with Tcl/Tk support, then run `build-windows.bat`. This installs the pinned PyInstaller build dependency and creates `dist/Hog/Hog.exe` with its adjacent `_internal` folder. Keep the whole output folder together. The script is included for reproducibility; no native Windows build or Windows execution was performed here.

## Build for the Current OS

```bash
python -m pip install -r requirements-build.txt
python tools/build_desktop.py
```

PyInstaller requires a Python shared library. Some Linux distributions package it separately (`libpython3.12` for the tested system). Build on the intended target OS; this is not cross compilation. `build-native.sh` provides a convenience wrapper for a Unix environment with pip available.

## Data Compatibility

The existing local `Hog/settings.json` and `Hog/hog.sqlite3` locations remain unchanged. Older preferences load with larger text disabled by default. v2.2.0 profile records, standard match history, and saved matches remain supported. Close the application before backing up its database.

## Installation Checks

`--version` needs no display. `--smoke-test` opens a desktop briefly and exits using temporary data. Full tests run with `python -m unittest discover -s tests -v`; GUI classes skip if a display is absent.
