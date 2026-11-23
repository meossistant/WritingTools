# Running Writing Tools from Source

Writing Tools uses [`uv`](https://docs.astral.sh/uv/) for fast, reproducible Python package management.

## 1. Install `uv`

- **Windows (PowerShell):**
  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
- **Linux:**
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

## 2. Sync Dependencies

From the repository root:
```bash
uv sync
```
`uv` automatically installs Python 3.12+ and all locked dependencies from `pyproject.toml` and `uv.lock`.

## 3. Run the Application

```bash
uv run writing-tools
# Or equivalently:
uv run python -m writing_tools
```

## 4. Run Tests

```bash
uv sync --group dev
QT_QPA_PLATFORM=offscreen uv run pytest
```

[Back to main README](../README.md)
