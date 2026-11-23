# Building Writing Tools with PyInstaller

1. Install [`uv`](https://docs.astral.sh/uv/).
2. Sync dependencies including the `build` group from the repository root:
   ```bash
   uv sync --group build
   ```
3. Run the PyInstaller build script:
   ```bash
   uv run --group build python scripts/build_pyinstaller.py
   ```

The standalone executable will be created in `dist/`.

## Automated Builds via GitHub Actions

This repository includes GitHub Actions workflows in `.github/workflows/`:
- **`ci.yml`**: Runs compile checks and the `pytest` test suite on `ubuntu-latest` and `windows-latest` on pushes/PRs to `main`.
- **`build.yml`**: Builds standalone Windows (`.zip`) and Linux (`.tar.gz`) PyInstaller executables on pushes to `main`, manual dispatches, and `v*` tags (automatically publishing a GitHub Release on `v*` tags).

[Back to main README](../README.md)
