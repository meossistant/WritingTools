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

[Back to main README](../README.md)
