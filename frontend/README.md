# JA4+ Forensics frontend

React, TypeScript and Vite interface for the FastAPI network-forensics backend.

## Local development

From this directory:

```powershell
npm ci
npm run dev -- --host localhost --port 5173 --strictPort
```

Or run `actions/start_frontend_windows.bat` from repository root. Open
http://localhost:5173; API requests use http://127.0.0.1:8001.

Backend, Zeek image, environment and model setup:
[project README](../README.md). Do not place backend credentials in Vite variables.

## Checks

```powershell
npm run build
npm run lint
```

Build output, dependencies, Flowbite generated metadata, local environment files
and browser-test artifacts are ignored. Commit the package lockfile with source.

The user interface includes PCAP upload, traffic, JA4+ fingerprints, network
subjects, anomaly investigations, periodic activity, behavior changes, history
and shared account settings. Administrator user management uses server-enforced
permissions. Administrator traffic/log pages and password recovery remain
incomplete; their presence in navigation is not evidence of implemented features.

Capture examples, SQLite databases and trained model weights are local artifacts
and are not distributed in this source repository.
