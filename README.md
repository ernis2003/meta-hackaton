# JA4+ Network Forensics Analysis

FastAPI + React network-forensics prototype: PCAP → Zeek → persistent subjects,
connections and graph → deterministic anomaly indicators → local Llama
explanations → Analysis History.

## Current verified state

Final verification on 2026-11-05 used existing capture files and the actual
trained adapter. No new traffic, fingerprints or model responses were fabricated.

- All three installed examples processed through real Docker/Zeek:
  normal.pcap: 80 connections, 11 subjects, 10 indicators;
  suspicious.pcap: 78 connections, 4 subjects, 2 indicators;
  mixed.pcap: 168 connections, 14 subjects, 7 domains, 12 indicators.
- Subject, connection, anomaly and graph APIs returned successful responses.
- The mixed analysis generated a fresh fine-tuned Llama response in 20.11 seconds.
  Saved-response retrieval and Analysis History reopening passed.
- Backend suite: all 47 tests passed with RUN_ZEEK_E2E=1 and RUN_JA4_E2E=1, including actual
  multipart capture upload, Docker/Zeek, persistence and graph reopening.
  Frontend production build passed.
- HTTP checks verified API :8001, Transformers :8002 and Vite localhost:5173.
  The frontend launcher reuses this project's existing healthy dev server.
- Profile, fingerprint and user-management pages have been browser-checked at
  desktop/mobile widths; account-management actions were also exercised.
- The configured JA4 image supports JA4, JA4S and JA4H. The official reference
  capture yielded 3 JA4, 4 JA4S and 1 JA4H values. See [JA4 setup](backend/zeek/README.md).

An indicator is not a malware verdict. Even the sample named normal.pcap triggers
periodicity rules. Sample filenames are not verified ground truth.

## Run the existing Windows demo

For a clean container deployment, run `docker compose up --build -d` from the
repository root, then open **http://localhost:8080**. Docker builds React/Nginx
and FastAPI with native Zeek and genuine JA4/JA4S/JA4H extraction. SQLite and the
generated JWT signing key persist in a named volume. No local `.env` is required
for the core application. The image installs the official FoxIO reference
capture; local sample captures and model weights are not bundled.

Fine-tuned Llama requires the optional NVIDIA GPU profile, authorized access to
the base model, and the existing adapter. See [Docker setup](docs/DOCKER.md) for
GPU/cache configuration, admin creation, persistence, and exact commands. The
core app works without inference; AI explanations require a reachable model
service. Muse additionally requires your own API credentials.

From repository root, in separate PowerShell terminals:

```powershell
.\actions\start_backend_windows.bat
.\actions\start_frontend_windows.bat
```

Open **http://localhost:5173**. Use the **User** login tab, or sign up for a
regular account. Admin accounts have a separate dashboard. Select Mixed sample,
open a subject in Network Subjects, then open Anomalies → AI Investigation →
Analyze with Llama. Reopen the analysis through Analysis History. Reports are
owned by the account that created the analysis.

The backend launcher checks Docker, reuses or starts the configured local
Transformers service, then starts FastAPI. GPU loading can take several minutes.
Do not start duplicate backend processes. API documentation:
http://127.0.0.1:8001/docs. Model health: http://127.0.0.1:8002/health.

Suggested 3-minute presentation: upload/sample (30s), graph and subject evidence
(45s), periodic finding and Llama (60s), saved history and limitations (45s).
Prewarm the model before presenting.

## Fresh setup

Prerequisites: Python 3.12, Node/npm, and Docker Desktop for Windows Zeek.
Fine-tuned inference additionally requires an NVIDIA CUDA GPU, the separate AI
environment, approved access to the gated base model, and the adapter artifacts.
A fresh clone does not include datasets, model weights, local captures or SQLite.

```powershell
py -3.12 -m venv backend/.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
Copy-Item backend/.env.example backend/.env
.\backend\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

Set JWT_SECRET_KEY in the private backend/.env to the generated value.
It must be at least 32 bytes. Keep optional ADMIN_EMAIL and ADMIN_PASSWORD empty
to use signup, or supply your own administrator credentials. Never commit .env.
ACCESS_TOKEN_EXPIRE_MINUTES is configurable.

```powershell
.\actions\build_zeek_ja4_windows.bat
.\backend\.venv\Scripts\python.exe actions/install_ja4_sample.py
Set-Location frontend
npm ci
Set-Location ..
```

The image build and reference-capture installer require network access once;
capture analysis itself runs offline. The example environment selects
ZEEK_MODE=docker, ZEEK_DOCKER_IMAGE=forensics-zeek-ja4:local and ZEEK_SCRIPTS=ja4.
For native Linux/WSL, run the backend there with ZEEK_MODE=native and optionally
ZEEK_BIN pointing to the installed Zeek binary.

For the existing trained adapter, configure backend/.env:

```dotenv
AI_RUNTIME=transformers
AI_SERVICE_URL=http://127.0.0.1:8002
AI_REQUIRE_FINE_TUNED=true
AI_ADAPTER_PATH=./src/ai/checkpoints/train/adapter
```

If the AI environment is missing, backend/setup_ai_windows.bat installs it;
this requires downloads and is not necessary for the prepared demo machine.
Do not run training to start the application. Baseline Ollama configuration is
also supported, but must not be described as fine-tuned inference.

Examples are a fixed allowlist of existing files in
backend/src/data/pcap_samples/: normal.pcap, suspicious.pcap, mixed.pcap and the
optional official foxio-latest.pcapng reference capture.
These local captures remain ignored and are not staged with source. Supply
legitimately available copies at those paths, or upload your own PCAP/PCAPNG.
Their original collection provenance is not established here; treat them as
demonstration evidence, not independently verified real-world attacks.
The optional official Zeek capture is served only when installed at
backend/examples/zeek-conn-size.pcap; it is not bundled in this checkout.

## Training evidence

Base: **meta-llama/Llama-3.2-3B-Instruct**, revision
0cb88a4f764b7a12671c53f0838cd831a0843b95.

Completed QLoRA artifacts are local at
backend/src/ai/checkpoints/train/adapter/. Weights:
adapter_model.safetensors, SHA256
f055fed559b10804a5c0b1ffc7ea5cdf85b260fad27626b462bc3f8a82bf8bc7.

Two epochs, 500 optimizer steps, NF4 4-bit, LoRA rank 8/alpha 16.
Training/validation/test: 2000/250/250 labeled-flow explanations from local
CTU-13, CIC-style Network Intrusion dataset and the folder named USTC-TFC2016.
Dataset identities are limited to inspected contents; folder labels alone are
not provenance. Training labels are supplied in prompts. There is no JA4
supervision and this is not a validated attack classifier.

Recorded training loss 0.0305802, validation loss 0.00392091, test loss
0.000221355. Original runtime 3169.8993s; finalization recovered from checkpoint
500. See training_metrics.json and training_manifest.json rather than treating
the recovery invocation's elapsed time as the full training time.

Before/after evaluation: 20 fixed authored scenarios, same protocol/base
revision. Strict JSON validity improved 4/20 → 12/20, while literal evidence
coverage decreased 0.85 → 0.525. Reasoning quality is mixed; low loss and valid
JSON do not establish forensic correctness.

Detailed workflow: [LLAMA_PIPELINE.md](docs/LLAMA_PIPELINE.md).
Local results, adapters and datasets remain ignored and require a separate
authorized distribution mechanism for independent reproduction.

## Known limitations

- The configured JA4 image extracts genuine JA4/JA4S/JA4H values. The original
  three local samples have no TLS ServerHello and therefore no JA4S, despite
  runtime support. Use the official reference capture to demonstrate all three.
  Historical analyses retain their original runtime capability metadata;
  reanalysis creates new results without deleting old evidence or AI reports.
- Muse review code, bounded read-only tools and persistence exist, but live
  review is unavailable without MODEL_API_KEY (or META_MUSE_API_KEY). No
  successful live Muse request is claimed. No credentials are bundled.
- Detection uses explainable volume/frequency/periodicity/novelty rules.
  Behavioral novelty needs earlier captures for the same user.
- SQLite schema v3 migrates automatically. Jobs are synchronous, intended for
  one worker; no distributed queue or automatic retry.
- Captures are limited to 100 MiB; Zeek timeout is 120s; logs are capped at
  200 MiB. Temporary captures/logs are removed. IP byte/packet totals describe
  conn.log, not every capture frame.
- CORS is configured for localhost:5173. Use the documented browser URL.
- Admin traffic/log pages and password recovery are unfinished; avoid them in
  the demo. Existing frontend lint findings remain; build success does not
  imply lint success.

## Tests

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
# Opt-in real capture test; requires an installed sample and working Docker:
$env:RUN_ZEEK_E2E='1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
Set-Location ../frontend
npm run build
npm run lint
```

Never stage credentials, SQLite, capture datasets, model weights or private
evaluation evidence. No Git commit or push is performed by the setup scripts.
