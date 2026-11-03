# meta-hackaton
This project implements digital forensics analysis and dependency graph building

## PCAP analysis with Zeek

Install backend dependencies: `pip install -r backend/requirements.txt`.
On Windows, start Docker Desktop and pull the analysis image:
`docker pull zeek/zeek:latest`.
The backend defaults to Docker on Windows and native Zeek on Linux.
Optional settings in `backend/.env`:

```dotenv
ZEEK_MODE=docker
ZEEK_DOCKER_IMAGE=zeek/zeek:latest
# For native Linux/WSL execution, run the backend there and use:
# ZEEK_MODE=native
# ZEEK_BIN=/opt/zeek/bin/zeek
```

Send an authenticated multipart request to `POST /api/analyses` (or the existing
`POST /api/pcap/analyze` alias), with
the capture in the `file` field and `Authorization: Bearer <access_token>`.
The endpoint is also available through FastAPI `/docs`.
It accepts PCAP/PCAPNG files up to 100 MiB and runs
`zeek -C -r capture.pcap LogAscii::use_json=T` in an isolated temporary directory.
`-C` ignores checksum errors, including captures affected by checksum offloading.
See [Zeek log documentation](https://docs.zeek.org/en/current/tutorial/logs.html).

The response contains the persisted analysis ID, final status, statistics,
capabilities, duration and status history. Failed jobs are saved and return an
HTTP error containing their analysis ID. Processing is synchronous; a completed
response is returned only after SQLite commits all result entities.

Start the backend with `actions\start_backend_windows.bat` (port 8001), then
run `npm run dev` in `frontend`. Sign in, upload a capture or select the official
Zeek example, and open Network Subjects. Traffic, fingerprints, anomalies and
history share the selected analysis. Reopening history never reruns Zeek.

Packet/byte totals come from conn.log and describe IP connections, not every
capture frame. Analysis times out after 120 seconds; parsing rejects logs larger
than 200 MiB. Raw captures and temporary Zeek logs are deleted after processing;
extracted entities and evidence are persisted per user. No fingerprints or
relationships are invented when evidence is missing.

See [pipeline, API, JA4 installation, rules and test results](docs/NETWORK_FORENSICS.md).
