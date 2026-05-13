# URGP CLI

**Command-line tool for CI/CD release ingestion and verification.**

The URGP CLI collects build metadata, computes artifact checksums, and transmits structured payloads to the URGP Event Gateway.

## Installation

```bash
cd cli
poetry install
```

## Usage

```bash
# Push a build to URGP
urgp-cli push \
  --product my-product \
  --release 1.0.0 \
  --build-type release \
  --build-id build-42 \
  --api-key $URGP_API_KEY \
  --server https://urgp.example.com \
  --commit-repo my-org/my-repo \
  --commit-hash abc123... \
  path/to/artifact.zip

# Verify a build's integrity
urgp-cli verify \
  --build-id build-42 \
  --api-key $URGP_API_KEY \
  --server https://urgp.example.com
```

## Commands

| Command | Description |
|---------|-------------|
| `push` | Collect build artifacts, compute SHA-256 checksums, and push to URGP Event Gateway |
| `verify` | Verify a build's integrity against the URGP control plane |

## Artifact Adapters

| Adapter | Type | Description |
|---------|------|-------------|
| Generic | `generic` | Any file — computes SHA-256, detects MIME type |
| Eclipse P2 | `eclipse_p2` | Eclipse update site — extracts IU metadata from `content.xml`/`content.jar` |

## Data Contract

The CLI produces payloads conforming to the URGP Data Contract v1.0 schema (`src/urgp_cli/contracts/data_contract.py`). Payloads include:

- Product/release/build metadata
- Artifact checksums (SHA-256)
- Commit hashes with repository references
- CI metadata (optional)

## Standalone Binary

Build a self-contained executable (no Python required):

```bash
cd cli
poetry run python scripts/build_cli.py
# Output: dist/urgp-cli (Linux) or dist/urgp-cli.exe (Windows)
```

## Development

```bash
# Run tests
poetry run pytest tests/ -v

# Lint
poetry run ruff check .

# Type check
poetry run mypy src/
```

## Project Structure

```text
cli/
├── src/urgp_cli/
│   ├── adapters/        # Artifact type adapters (generic, eclipse_p2)
│   ├── commands/        # push, verify subcommands
│   ├── contracts/       # Data contract schema
│   ├── transport/       # HTTP client with retry logic
│   ├── checksum.py      # SHA-256 computation
│   ├── output.py        # Rich console output formatting
│   └── main.py          # Typer app entry point
├── tests/
├── scripts/             # PyInstaller build script
└── urgp-cli.spec        # PyInstaller spec
```
