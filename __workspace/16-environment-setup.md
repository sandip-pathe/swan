# Environment setup — 15 November 2026

## Installed and configured

- Node.js 24.22.3 LTS and bundled npm, workspace-local; official distribution SHA-256 verified.
- uv 0.13.8, workspace-local; Python 3.13.17 installed through the official Python Windows package using WinGet.
- `.venv` with FastAPI, SQLAlchemy, Alembic, Psycopg, Pydantic settings, Uvicorn, pytest, Ruff, mypy and HTTPX; `uv.lock` records exact versions.
- PostgreSQL 17.12 runtime from EDB's official Windows archive, with database `swan_trade` on loopback port 54329, SCRAM password authentication and ignored local connection configuration. Only runtime folders were extracted; graphical management tools were not installed.
- Microsoft Visual C++ runtime installed through WinGet to satisfy PostgreSQL dependencies.
- Frontend dependencies installed and locked, Firebase configuration retained locally, patched gRPC override applied.
- Project activation, database start/stop/status and frontend launch scripts; root usage documentation.

## Verified

- Frontend production build and TypeScript check pass after the dependency override.
- Production dependency audit reports zero vulnerabilities.
- Frontend HTTP smoke check returns 200 with the sign-in page.
- Backend framework imports pass.
- Authenticated PostgreSQL connection and exact numeric round-trip pass in a rolled-back temporary transaction.
- PostgreSQL stop/start and reconnect pass.
- Environment verification script passes Ruff checks.

These are environment checks, not evidence that the trading engine or full product is complete. Live Firebase sign-in, backend Firebase authorization, broker/news integrations and AI workflows remain unverified or unimplemented.

## Windows compatibility notes

Windows application control blocked the uv-managed Python distribution; the official Python installer worked. It also blocked Psycopg's bundled native module; the supported pure-Python driver with the installed PostgreSQL libpq works. No application-control policy was disabled.

WinGet's default Delivery Optimization download route stalled. A temporary user setting selected the documented WinINet downloader and was removed after installation, restoring the original settings. No package hash, certificate, malware or application-control checks were disabled.

Git remains uninstalled: the official WinGet installer and checksum-verifiable MinGit release download timed out. Retry the official Git for Windows download when connectivity permits; this does not block local runtime or database work, but source-control initialization remains pending. Environment files have filesystem access restricted to the current user and SYSTEM.

## Step-one status

The runtime, database and package dependencies required for step one are ready. Implement schemas/migrations, risk sizing, paper execution, ledger and meaningful fixture tests next. No broker, news or OpenAI key is needed for those deterministic modules. Git installation status is tracked in the completion report if unavailable.

Official references: [Node distributions](https://nodejs.org/dist/), [uv installation](https://docs.astral.sh/uv/getting-started/installation/), [PostgreSQL Windows distribution](https://www.postgresql.org/download/windows/), [WinGet network settings](https://learn.microsoft.com/en-us/windows/package-manager/winget/settings).
