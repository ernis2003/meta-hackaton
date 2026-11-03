# Network forensics implementation

This extends the existing FastAPI/React application. The inspected repository
uses Python's sqlite3 directly, not SQLAlchemy. Existing user CRUD and SQLite
connections are retained. The PCAP service is `backend/src/pcap_analysis.py`;
there was no `backend/src/service/pcap_analysis.py`, history store, or anomaly
engine in this checkout. Existing related dashboard pages were shells.

## Run

1. Start Docker Desktop. `docker pull zeek/zeek:latest`.
2. Install `backend/requirements.txt` into `backend/.venv`.
3. Configure `backend/.env`, including a random `JWT_SECRET_KEY` of at least
   32 bytes. Do not commit that file.
4. Run `actions\start_backend_windows.bat`. It resolves its directory and starts
   the virtual environment's Python on port 8001, matching frontend constants.
5. In `frontend`, run `npm install` and `npm run dev`. Open localhost:5173,
   sign in, and upload a PCAP/PCAPNG or choose the supplied Zeek capture.
6. Network Subjects opens after successful processing. Select stored analyses
   in the shared selector or Analysis History to review results without upload.

For native Linux/WSL execution, run the backend there with `ZEEK_MODE=native`
and optionally `ZEEK_BIN=/opt/zeek/bin/zeek`. On Windows Docker is the default.

## Processing and storage

SQLite data now defaults to `backend/src/database/migrations/app.sqlite3`.
Relative `DATABASE_PATH` values resolve from `backend`, regardless of the
launch directory. Database files in that folder are ignored by Git; migration
SQL files remain versioned and must be included when sharing the repository.

The request creates a pending record, commits processing, validates and analyzes
the capture in a private temporary directory, parses every record within the
200 MiB cumulative log limit, derives relationships, and commits the entities
and completed status together. Failures persist their final failed status and
safe error before returning an HTTP error. No successful response is returned
while processing is unfinished. The upload view shows an indeterminate
processing status; it does not invent percentage progress.

Startup applies the additive, idempotent migration
`backend/src/database/migrations/001_analyses.sql`. It adds `analyses`,
`analysis_entities`, and `analysis_status_events`, indexes, cascading foreign
keys, status constraints, and audit triggers. Schema version is 1. Result
entities are stored individually by analysis, kind and stable ID, with JSON
attributes. This is a compact entity store rather than separate ORM tables;
there is no duplicate persisted graph snapshot. Graphs are reconstructed from
subjects, fingerprints and directed relationships. Connections retain their
correlated protocol evidence. User deletion cascades to their analyses.

The current executor is synchronous and intended for a single backend worker.
Startup marks interrupted pending/processing records failed; it does not retry
them. A durable distributed job queue, concurrent worker recovery, retention
and deletion controls are outside this implementation. Large histories are
paginated, but baseline construction and graph reconstruction still read the
relevant persisted entities into memory.

## Evidence and fingerprints

All JSON Zeek logs are parsed, including conn, dns, ssl and http. Connection UIDs
correlate TLS/HTTP and other UID-bearing records. DNS has a separate resolver
UID, so address/name attribution uses DNS answers, the originating client,
capture timestamps and answer TTL. Missing TTL gives no extended validity
window. DNS names are not treated as proof of a physical device identity.
IP subjects are address observations, including shared addresses and NAT.

Each directed source/destination pair aggregates repeated communication while
retaining connection IDs, ports, protocols and volume. TLS SNI and HTTP Host,
or a temporally valid DNS answer and matching session, provide domain edges.
Fingerprint edges are attached to the TLS client for JA4, TLS server for JA4S,
and HTTP originator for JA4H. The original protocol record and log field remain
available as source evidence. JA3 is never relabeled as JA4.

Runtime inspection executes Zeek's version and inspects SSL::Info/HTTP::Info
record fields with the same configured scripts. Supported but unobserved
methods report `no_applicable_traffic`; absent fields report `unsupported`;
an unsuccessful probe reports `unavailable`. Actual extracted values report
`extracted`. Captures with no applicable TLS/HTTP can have zero fingerprints.

The tested default Docker image runs Zeek **9.0.1** and has **no active JA4,
JA4S or JA4H log fields**. To enable these, install FoxIO's JA4 package in your
Zeek runtime, for example `zkg install zeek/foxio/ja4`, and make its scripts or
plugins available. For script packages set `ZEEK_SCRIPTS=packages` in
`backend/.env`; it is passed to both schema inspection and packet analysis.
When using Docker, install the package into a custom image and set
`ZEEK_DOCKER_IMAGE` to that image. Installing into a disposable `--rm` container
does not persist it. Zeek 5+ is documented upstream; QUIC requires 6+.
Check upstream build requirements and the JA4+ license before distribution.
See [FoxIO's installation and compatibility documentation](https://github.com/FoxIO-LLC/ja4/blob/main/zeek/README.md).

## Deterministic indicators

These are explainable triage indicators, not malware verdicts:

| Indicator | Rule | Severity | Risk contribution |
| --- | --- | --- | --- |
| Frequent connections | At least 100 sessions per directed pair in a rolling 60-second window; one indicator per pair | Medium | 25 |
| Periodic communication | At least 6 sessions, mean interval at least 1 second, interval standard deviation / mean at most 0.1 | Low | 15 |
| High traffic volume | At least 100 MiB of observed IP bytes per directed pair | Medium | 25 |
| New destination | Previously observed originator contacts a destination absent from that user's historical pairs | Low | 10 |
| New fingerprint | Fingerprint absent from the user's available history on a connection from a previously observed originator | Low | 10 |

Only previously completed analyses belonging to the same user contribute to
history. Historical sessions must end before the current capture's first
session; re-uploading the same capture or uploading older traffic cannot create
a future-derived baseline. No historical data means no novelty indicators.
Novelty is informational and is not inherently malicious. Shared addresses
remain ambiguous across captures. Host risk is the sum of associated indicator
contributions capped at 100. Both participants are associated with each pair
indicator. Every indicator records its rule, observed values, connection IDs,
subject IDs and capture timestamp. Risk 60+ renders red, other indicators
orange, with explicit counts and labels as well as color.

## API

Every endpoint requires the existing bearer authentication. Analyses are scoped
to their owner, including administrators; another user's analysis returns 404.

| Method | Path | Behavior |
| --- | --- | --- |
| POST | /api/analyses | Multipart `file`; synchronously returns completed analysis, 201 |
| POST | /api/pcap/analyze | Existing route, same persisted pipeline; returns analysis metadata |
| GET | /api/analyses | Paginated owner history |
| GET | /api/analyses/examples | Installed capture examples |
| POST | /api/analyses/examples/{name} | Analyze a whitelisted installed example |
| GET | /api/analyses/{id} | Metadata, summary, capabilities and status audit |
| GET | /api/analyses/{id}/status | Same current processing state |
| GET | /api/analyses/{id}/graph | Reconstructed graph, `search`, `focus`, `limit` |
| GET | /api/analyses/{id}/subjects | Paginated subjects |
| GET | /api/analyses/{id}/connections | Paginated sessions and correlated evidence |
| GET | /api/analyses/{id}/fingerprints | Paginated actual extracted values |
| GET | /api/analyses/{id}/anomalies | Paginated evidence; optional subject_id, connection_id, anomaly_type, anomaly_ids filters |
| GET | /api/analyses/{id}/relationships | Paginated directed relationships |

Collection responses are Pydantic envelopes `{items,total,limit,offset}`.
`limit` defaults to 50 for results (maximum 200) and 25 for history (maximum
100). Graph defaults to 300 nodes (maximum 1000) and caps edges at 2000.
Search and neighborhood filtering happen before these display limits. Graph
metadata samples connection IDs/partners at 200, marking truncation and total
counts; full persisted connections remain accessible through paginated APIs.
The frontend provides pan/drag, zoom controls, minimap, Dagre layout, selection,
search, type filtering, related-node highlights, neighborhood focus, reset and
fullscreen. Selected analysis is kept in session storage across dashboard pages
and cleared on authentication/logout. Analysis changes remount result views.

## Verification and sample provenance

Run backend tests from `backend`:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
$env:RUN_ZEEK_E2E='1'
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Setting RUN_ZEEK_E2E requires working Docker/Zeek and actually runs the capture
through authenticated API upload, Zeek, SQLite persistence and graph reopening.
All databases used by tests are temporary. Unit tests mock Zeek logs only for
specific parsing and rule assertions; production has no fixture result path.
Run `npm run build` in `frontend` for TypeScript and production bundling.

Final validation: all **25 backend tests passed**, including the real Zeek
end-to-end test; the frontend production build passed. Existing FastAPI test
support emits an httpx deprecation warning, without test failures.

The requested `normal.pcap`, `suspicious.pcap`, and `mixed.pcap` are absent from
the inspected checkout, so no results are claimed for them. The supplied
`backend/examples/zeek-conn-size.pcap` is the unmodified 2823-byte
[official Zeek conn-size.pcap capture](https://github.com/zeek/zeek/blob/master/testing/btest/Traces/conn-size.pcap),
downloaded on 2026-11-03. Its PCAP header was checked before real processing.
Upstream licensing is retained in `backend/examples/ZEEK-LICENSE.txt`.

SHA256: `fe4c4cda617518de5663697cc8ba8483b42d9de951b7204087caf173b1b162e2`.

Actual Zeek 9.0.1 output in the end-to-end test:

| Metric | Value |
| --- | --- |
| Connections | 5 |
| IP subjects | 8 |
| Domains | 1 |
| IP packets / bytes from conn.log | 21 / 2121 |
| Protocol sessions | TCP 2, UDP 2, ICMP 1 |
| HTTP sessions | 1 |
| JA4+ values | 0; unsupported in this runtime |
| Indicators | 0 |

No normal/suspicious verdict is assigned to this capture. No interactive browser
automation is available in this session; UI checks cover TypeScript/build, not
visual browser verification.

## Changed implementation areas

- `backend/src/pcap_analysis.py`: shared validation/runtime/log reader, full-log
  extraction option, JA4 capability probe, persistent legacy route.
- `backend/src/forensics.py`: evidence correlation, subjects, relationships,
  fingerprints, deterministic indicators and graph reconstruction.
- `backend/src/analyses.py`: authenticated analysis lifecycle, persistence,
  metadata/history, result pagination, examples, graph filtering.
- `backend/src/database/connection.py`, `migrations.py`, migration SQL: startup
  schema upgrade and status auditing.
- `backend/main.py`: new router registration.
- `frontend/src/utils/analyses.ts`: typed API access and shared selection;
  `utils/auth.ts`: selection reset on account change/logout.
- Existing business pages plus shared `AnalysisResults.tsx` and
  `EvidenceDetails.tsx`: real uploads, history and evidence presentation.
- `NetworkSubjects.tsx`: React Flow graph and evidence inspector;
  `App.tsx`: graph loaded on demand.
- `frontend/package.json` and lockfile: new `@xyflow/react` and
  `@dagrejs/dagre`; no new Python or ORM dependency added by this work.
- `backend/tests/test_analyses.py`, official example, launch script and docs.
