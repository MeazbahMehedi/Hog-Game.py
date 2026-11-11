# Prepare the GitHub Release

The project is packaged for your review. This ZIP has not created a GitHub tag, uploaded a release, deployed a relay or executed the supplied GitHub Actions workflow.

## Source and release fields

1. Extract `hog-v4.0.0.zip` and copy the project contents into your repository working folder. Keep the README, source, tests, screenshots and documentation together.
2. Commit the reviewed changes. Do not commit your personal settings, databases, backups or diagnostic logs.
3. On GitHub, open **Releases > Draft a new release** and choose the intended source commit/branch.
4. Create/select tag **`v4.0.0`**.
5. Use title **`v4.0.0 - Complete Desktop Edition`**.
6. Copy the description from [RELEASE_NOTES.md](../RELEASE_NOTES.md).
7. Attach the delivered ZIP, inspect the rendered README/images and save a draft or publish when ready.

The README includes the current release, earlier version details and historical screenshots. Its relative links depend on retaining the supplied directory structure.

## Native platform artifacts

The ZIP includes a Linux x86-64 native client tested here on glibc 2.39. Windows and macOS build recipes are included, with their unverified status stated in the release notes. Build those artifacts on their target OS before attaching them or calling them tested.

The manual **Native builds (manual validation artifacts)** workflow is in `.github/workflows/native-builds.yml`. Push the project to your repository root, open GitHub Actions and run the workflow. It builds a three-platform matrix, runs tests/network/doctest checks and produces downloadable build artifacts. It does not create or publish a release.

Inspect all job logs, including GUI test skips, and test installers on clean target machines. Native output can depend on runner architecture, OS libraries and Python/Tk availability. Windows/macOS packaging here is unsigned; signing/notarization require your own credentials and release process. No credentials are provided or requested by the project.

For commands, read [INSTALL.md](../INSTALL.md). For runtime notices, retain the native third-party notices and the original project/starter-code attribution.
