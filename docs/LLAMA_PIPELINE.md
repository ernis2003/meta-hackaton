# Llama QLoRA and Meta Muse

Paths below are relative to `backend`. Generated datasets, results, checkpoints
and adapters are ignored by Git and retained locally.

## Execution and local data

The RTX 5070 Laptop GPU has 8,151 MiB VRAM, compute capability 12.0.
CUDA forward/backward and official Hugging Face model-config access passed.
The existing AI environment has PyTorch 2.9.1+cu128, Transformers 4.57.6,
PEFT 0.18.1, TRL 0.26.2 and bitsandbytes 0.49.2. See
`src/ai/results/preflight.json` for actual checks.

Preparation completed with 2,000 training, 250 validation and 250 test records.
All 2,500 conversations fit 512 tokens. Schemas, observed labels, source rows,
capture groups and hashes are in `datasets/prepared/provenance.json`;
token counts and overlap checks are in `results/dataset_validation.json`.

The requested two-epoch run completed all 500 optimizer steps. Actual average
training loss: 0.0305802; final validation loss: 0.00392091; held-out test loss:
0.000221355. Peak PyTorch allocation was 4,719,290,880 bytes (4.40 GiB), and
training runtime was 3,169.8993 seconds. See
`checkpoints/train/training_metrics.json` for optimizer-run metrics.
Finalization initially failed because the held-out dataset was not tokenized;
this was fixed and resumed from checkpoint 500 without additional optimizer
updates. The adapter manifest's elapsed time and VRAM describe that recovery
invocation; the metrics sidecar retains the full original training run.
The original failure record and recovery log are preserved.

`datasets/training_data/` is the existing local source directory:

| Folder | Actual inspected contents and use |
| --- | --- |
| CTU-13 | Parquet with dur, proto, tot_pkts, tot_bytes, src_bytes, label, Family. Detailed labels preserved; background is not assumed benign. |
| Network Intrusion dataset | CIC-style numerical flow CSVs and Label: BENIGN, DDoS, PortScan, Bot, web attacks and other labels. |
| USTC-TFC2016 | Dated 2018 flow CSVs with abbreviated fields and Label, despite the folder name. Repeated headers rejected. Dataset identity is not assumed from the folder name. |
| IDS 2018 Intrusion CSVs | PCAPs under benign/malware folders, despite the folder name. Excluded: folder names alone do not establish per-flow ground truth. |

Only finite observed fields and supplied labels are used. No JA4 values,
attack mechanisms, units or endpoint context are invented. Labels are explicit
prompt evidence; answers distinguish annotations from verified diagnoses.
This teaches labeled-flow explanation, not a validated classifier or JA4 detector.

Samples span batches throughout each file, with bounded per-label candidate
pools and round-robin source/label selection. This is not an unbiased prevalence
estimate. CTU variants are grouped into Botnet/Normal/Background for sampling
only. Capture days stay in one split, including same-day CTU scenarios and CIC
weekday files. Identical selected feature evidence is excluded globally, even
with different labels. Fixed authored evaluation scenarios are not training
records. Raw datasets remain unchanged.

```powershell
.\.venv-ai\Scripts\python.exe -m src.ai.datasets.prepare
```

Nonempty artifacts are preserved. Use `--output` for another preparation, then
pass that directory with `--dataset` to training. `prepared_initial` retains the
initial sampling output; balanced preparation is in `prepared`.

## Baseline, training and evaluation

```powershell
.\.venv-ai\Scripts\python.exe -m src.ai.evaluation.evaluate --stage before
.\.venv-ai\Scripts\python.exe -m src.ai.training.preflight --require-cuda
.\.venv-ai\Scripts\python.exe -m src.ai.training.smoke_test
.\.venv-ai\Scripts\python.exe -m src.ai.training.train_qlora
.\.venv-ai\Scripts\python.exe -m src.ai.evaluation.evaluate --stage after --adapter src/ai/checkpoints/train/adapter
.\.venv-ai\Scripts\python.exe -m src.ai.evaluation.compare_models
```

Or run `backend\train_model_windows.bat` from repository root. It prepares missing
data, evaluates baseline, verifies CUDA, smoke-tests the actual model, trains,
evaluates and compares in separate processes to release VRAM. Approved Hugging
Face access and local authentication are required.

The only base is `meta-llama/Llama-3.2-3B-Instruct`. Defaults: NF4 4-bit double
quantization, rank 8, alpha 16, dropout 0.05, q/k/v/o projections, 2 epochs,
batch 1, accumulation 8, LR 2e-4, length 512, gradient checkpointing.
CPU placement/offload is refused. A real-model two-step smoke must save an
adapter and checkpoints before full training. Synthetic tests cannot satisfy
this gate. No fallback configuration is selected automatically.

Checkpoints are retained. Training saves loss/VRAM logs, final adapter, tokenizer,
manifest and held-out test loss. Resume with `--resume latest`; dataset/config/base
hashes must match. Interrupted runs are marked incomplete and do not run after
evaluation. Missing outputs never imply success.

Twenty authored scenarios are in `evaluation/control_questions.json`. Before/after
use identical questions, evidence, prompts, schema, greedy settings, NF4 runtime
and immutable base revision. Actual responses and parse failures are saved
incrementally to `results/before_training.json` and `after_training.json`.
Completed evaluations are preserved.

`results/comparison.md` includes actual responses, strict JSON validity and
evidence/limitation token coverage. These are proxies. Semantic correctness,
unsupported claims and explanation quality require review; valid JSON does not
establish correctness. No improvement is asserted automatically.

## Application inference

The normal backend imports no training dependencies. Its existing Ollama baseline
continues working without Muse. Metadata distinguishes baseline and fine-tuned
reports. Cached reports retain their original identifiers.

To serve a completed adapter:

On Windows, `actions/start_backend_windows.bat` automatically starts the local
Transformers service configured in `backend/.env` and waits for its health check
before starting the API. An already healthy service is reused. Startup output is
saved in `backend/src/ai/results/model_service.log`. The completed adapter's
pinned model snapshot is reused from the local Hugging Face cache when available.
For a standalone model service, run the following from `backend`:

```powershell
$env:AI_ADAPTER_PATH=(Resolve-Path 'src/ai/checkpoints/train/adapter').Path
.\.venv-ai\Scripts\python.exe -m uvicorn src.ai.llm.server:app --host 127.0.0.1 --port 8002
```

Backend environment: `AI_RUNTIME=transformers`,
`AI_SERVICE_URL=http://127.0.0.1:8002`, `AI_REQUIRE_FINE_TUNED=true`.
The service rejects incomplete, smoke-only, wrong-base and checksum-mismatched
adapters. No model substitution or CPU training occurs.

Anomalies → AI Investigation provides **Analyze with Llama** and
**Investigate with Meta Muse**. Saved reports load without inference. Responses,
evidence, conclusions, self-reported confidence and model identifiers are shown.
Errors never become fabricated successful reports.

## Independent Meta Muse review

Official references: [quickstart](https://dev.meta.ai/docs/quickstart),
[Chat Completions](https://dev.meta.ai/docs/protocols/chat-completions),
[tool calling](https://dev.meta.ai/docs/tool-calling).

Backend-only environment; never expose these as Vite variables:

```dotenv
MODEL_API_KEY=
META_MUSE_MODEL=muse-spark-1.3
META_MUSE_BASE_URL=https://api.meta.ai/v1
META_MUSE_MAX_TOOL_CALLS=4
```

Muse receives structured database evidence and the saved Llama report, never PCAP
bytes. It independently checks observations, identifies unsupported claims,
considers benign alternatives and recommends investigation. Validated JSON has
`verdict`, `summary`, `verified_observations`, `unsupported_claims`,
`benign_explanations`, `recommended_actions`, `confidence`.

Tools retrieve related connections, host profiles, JA4 fingerprints and stored
periodic-activity findings. They accept no model-provided SQL, paths, analysis IDs
or arbitrary parameters. Every retrieval rechecks access to the selected analysis.
Results and list fields are capped at 20 with truncation indicators. Default
budget: four calls; hard limit: eight. Tool results are saved for audit.

Existing bearer authorization and ownership checks protect both roles:

```text
GET  /api/analyses/{analysis_id}/anomalies/{anomaly_id}/explanation
POST /api/analyses/{analysis_id}/anomalies/{anomaly_id}/explain
GET  /api/analyses/{analysis_id}/anomalies/{anomaly_id}/review
POST /api/analyses/{analysis_id}/anomalies/{anomaly_id}/investigate
```

POST accepts `?regenerate=true`. Migrations 002/003 add separate saved reports and
leases. Concurrent duplicate work returns 409. Changed Llama reports invalidate
Muse cache reuse; old reviews are marked stale. Missing credentials, API errors
and invalid JSON leave local Llama usable.

## Verification

Backend: `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`.
The complete suite has 47 tests. All passed with RUN_ZEEK_E2E=1 and
RUN_JA4_E2E=1; ordinary runs skip those two runtime-dependent checks. Mocked Muse tests cover
authorization, retrieval, persistence, cache staleness, tool limits, schema
validation and failure isolation. They are not real model results.

Frontend production build passes. The pre-publication audit reports ten lint
errors across AnalysisList, AnalysisResults, BehaviorChanges, EvidenceDetails,
NetworkSubjects and SubjectActivity. Profile, fingerprints and administrator
user management were browser-checked at desktop/mobile widths. No Meta API key was configured, so live Muse access remains
unverified until backend credentials are supplied.
