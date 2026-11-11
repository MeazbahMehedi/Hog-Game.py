# Native Desktop Package — v4.0.0

The `linux-x86_64/Hog/` directory contains the tested one-folder Linux x86_64 build. Keep the entire folder together.

```bash
chmod +x linux-x86_64/Hog/Hog
./linux-x86_64/Hog/Hog
```

From the project root, the path is `native/linux-x86_64/Hog/Hog`.

Built on Linux with glibc 2.39, Python 3.12.3, Tk 8.6, and PyInstaller 6.22.3. Rebuilt for v4.0.0. Verified with `--version` and a real-window `--smoke-test`. It still needs a graphical Linux desktop and system graphics libraries. Compatibility with older glibc versions is not claimed.

A Windows executable is not included. On Windows, run `build-windows.bat` with Python 3.10+ and Tk installed to build `dist/Hog/Hog.exe` locally. This script installs the pinned optional packaging dependency. Native packages must be built on their target OS. The Python source remains the portable option.

Collected system runtime copyright notices are provided in `THIRD_PARTY_NOTICES/`. Original application/starter-code attribution is in the main README.

The v4.0.0 binary includes the multiplayer client and TLS support. Start a separate relay using `python hog_server.py` from the project source. See [ONLINE.md](../ONLINE.md) for connection and hosting instructions.

For per-user Linux installation, Windows installer recipes, the macOS DMG builder and platform verification status, read [INSTALL.md](../INSTALL.md). The installer preserves per-user progress.
