# JA4+ Network Forensics Analysis

**Turn packet captures into explainable network investigations with JA4+ fingerprints and fine-tuned Meta Llama.**

JA4+ Network Forensics Analysis helps analysts explore captured network activity, identify suspicious patterns, and understand the evidence behind each finding.

The platform combines **packet analysis**, **network visualization**, **deterministic anomaly detection**, and **local AI explanations** into a persistent investigation workflow.
<img width="2530" height="1262" alt="image" src="https://github.com/user-attachments/assets/df9ed6b7-913f-406e-a567-f84b24bc38bd" />

---

## Why This Project?

Packet captures contain technical evidence, but discovering relationships and deciding what to investigate next takes time.

| Analyst question | What the platform provides |
| --- | --- |
| **What communicated?** | Explore subjects, connections, domains, and a network graph. |
| **Which fingerprints appeared?** | Inspect genuine JA4, JA4S, and JA4H values extracted by Zeek. |
| **What deserves attention?** | Review explainable indicators such as periodic connections and unusual activity. |
| **Why was it flagged?** | Ask fine-tuned Meta Llama to interpret recorded evidence and suggest investigation steps. |
| **Can the investigation be reopened?** | Analyses and generated explanations are saved in SQLite. |

## Meta AI Contribution

The AI explanation workflow uses **[`meta-llama/Llama-3.2-3B-Instruct`](https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct)**, fine-tuned locally with **QLoRA**.

When an analyst selects an anomaly, the backend retrieves its stored evidence and sends a structured evidence package to the local inference service. The model returns an explanation covering **observations, hypotheses, benign alternatives, and recommended investigation steps**.

The application saves the response, supporting evidence, and model identifiers so the investigation can be reopened later.

> **Detection ≠ explanation.** Deterministic rules flag activity; Llama helps interpret the evidence. Model output requires analyst review.

### Meta Integration Status

| Integration | Status |
| --- | --- |
| Llama 3.2 3B Instruct | Live local inference verified |
| QLoRA adapter | Fine-tuned and loaded successfully |
| Fresh anomaly explanation | Verified end to end and saved |
| Before/after evaluation | Completed on 20 fixed authored scenarios |
| Meta Muse review | Integration implemented; live API request not verified |

---

## Quick Start

### Requirements

- Docker Desktop or Docker Engine
- Docker Compose v2
- Linux containers

### 1. Build and Start

Run from the repository root:

```bash
docker compose up --build -d
```

### 2. Open the Application

- **Web app:** http://localhost:8080 — create an account to begin.
- **API documentation:** http://localhost:8080/docs

### Included in the Default Deployment

- React production frontend served by Nginx
- FastAPI backend
- Native Zeek with JA4, JA4S, and JA4H support
- Persistent SQLite storage
- Automatically generated, persistent JWT signing key
- Official reference capture for fingerprint extraction

> **Note:** The first build needs internet access to download dependencies and pinned upstream reference files. Core capture analysis requires neither a GPU nor a paid API.

### 3. Enable Fine-Tuned Llama (Optional)

AI explanations additionally require:

- An NVIDIA GPU with sufficient VRAM
- Authorized access to `meta-llama/Llama-3.2-3B-Instruct`
- The completed project adapter
- Either the optional GPU inference container or a compatible existing local inference service

After configuring the adapter and model access:

```bash
docker compose --profile gpu up --build -d
```

**Model weights and the adapter are not included in Git.** A fresh clone runs the core forensic application, but fine-tuned explanations require these separate artifacts.

See **[Docker Setup](docs/DOCKER.md)** for GPU, cache, credentials, administrator, and persistence instructions.

---

## Investigation Workflow

```text
PCAP / PCAPNG
      |
      v
Zeek + JA4 extraction
      |
      v
Stored connections, subjects, domains, and fingerprints
      |
      v
Network graph + deterministic anomaly indicators
      |
      v
Fine-tuned Llama explanation
      |
      v
Saved analysis and AI report
```

### Technology Stack

| Component | Implementation |
| --- | --- |
| **Frontend** | React, TypeScript, Vite, Tailwind |
| **API** | FastAPI |
| **Capture processing** | Zeek with FoxIO JA4 scripts |
| **Fingerprints** | JA4, JA4S, JA4H |
| **Persistence** | SQLite with automatic schema migrations |
| **Authentication** | JWT with server-side access controls |
| **AI inference** | Transformers, PEFT, bitsandbytes |
| **Deployment** | Docker Compose, Nginx, optional NVIDIA GPU service |

Analyses belong to the account that created them. Generated explanations are stored alongside their evidence and model metadata.

---

## Verified Results

**Verification date: November 5, 2026.**

| Check | Observed result |
| --- | --- |
| Docker frontend and backend | Both started and became healthy |
| Frontend production build | Passed |
| Official FoxIO reference capture | **33 connections; 3 unique JA4, 4 JA4S, 1 JA4H** |
| Existing local `mixed.pcap` upload | **168 connections and 12 rule findings** |
| Network graph | Retrieved successfully |
| Fine-tuned Llama | Generated a fresh explanation through the container backend using the existing host inference service |
| Latest measured explanation time | **14.33 seconds** on the prepared machine |
| AI persistence | Saved explanation retrieved successfully |
| Analysis History | Both test analyses available |
| Backend restart | Accounts, JWT session, analyses, and explanation preserved |
| Backend test suite | Previously verified: **47 tests passed** with real Zeek/JA4 integration checks enabled |

> **Verification boundary:** The optional GPU container configuration was validated, but its image build and containerized model loading have **not** been verified. Successful inference used the already running host model service.

---

## QLoRA Training and Evaluation

The adapter was trained on the actual Meta Llama model.

### Training Configuration

| Setting | Value |
| --- | --- |
| Base model | `meta-llama/Llama-3.2-3B-Instruct` |
| Base revision | `0cb88a4f764b7a12671c53f0838cd831a0843b95` |
| Method | QLoRA, NF4 4-bit quantization |
| LoRA rank / alpha | 8 / 16 |
| Epochs / optimizer steps | 2 / 500 |
| Train / validation / test records | 2,000 / 250 / 250 |
| Local adapter directory | `backend/src/ai/checkpoints/train/adapter/` |

Training used labeled-flow explanations derived from inspected local CTU-13 data, CIC-style intrusion-flow CSVs, and CSVs stored in a folder named `USTC-TFC2016`. Dataset identity is **not** assumed from folder names alone.

**Training scope:** Labeled-flow explanation, not JA4 supervision. These results do **not** establish attack-classification accuracy.

### Before vs. After Fine-Tuning

Evaluation used **20 fixed authored scenarios** with the same base revision and evaluation protocol.

| Metric | Base model | Fine-tuned model |
| --- | ---: | ---: |
| Strict JSON validity | 4/20 | **12/20** |
| Literal evidence coverage proxy | **0.85** | 0.525 |

Fine-tuning improved output-format compliance, while measured evidence coverage decreased. **Results are mixed and do not establish improved forensic correctness.**

For training manifests, adapter checksums, evaluation scripts, and the detailed procedure, see **[Llama Pipeline](docs/LLAMA_PIPELINE.md)**. Generated artifacts remain local and require separate authorized distribution for independent reproduction.

---

## Genuine JA4+ Fingerprint Extraction

Fingerprint values come from **actual Zeek output**, not generated examples.

| Fingerprint | Purpose |
| --- | --- |
| **JA4** | TLS client fingerprint |
| **JA4S** | TLS server fingerprint |
| **JA4H** | HTTP client fingerprint |

A supported fingerprint type may still return zero results if the necessary traffic is absent. For example, captures without TLS ServerHello messages cannot yield JA4S values.

The official reference capture demonstrates all three types. See **[JA4 Setup and Reference Capture](backend/zeek/README.md)**.

---

## Current Scope and Limitations

- Findings are **triage indicators**, not malware verdicts. Sample filenames do not establish ground truth.
- Llama explanations can contain mistakes and require review against recorded evidence.
- Meta Muse review code and persistence are implemented, but no successful live Muse request is claimed.
- Behavioral novelty comparisons require earlier analyses for the same user.
- Processing is synchronous and intended for a single backend worker.
- Uploads are limited to **100 MiB**, with a **120-second** Zeek processing timeout.
- Administrator traffic/log pages and password recovery are unfinished.
- Frontend production builds pass; existing lint findings remain.
- This is a **hackathon prototype**, not a production-certified intrusion detection system.

## Repository and Data Boundaries

The repository contains application source, deployment configuration, training and evaluation code, and documentation.

The repository **excludes** private credentials, SQLite databases, local capture datasets, base-model weights, and adapter weights. Docker downloads the pinned official reference capture during its build.

## Documentation

| Guide | Description |
| --- | --- |
| [Docker Deployment](docs/DOCKER.md) | Setup, GPU, credentials, administration, and persistence |
| [Llama Training and Inference](docs/LLAMA_PIPELINE.md) | Training, evaluation, and inference procedure |
| [JA4 Extraction](backend/zeek/README.md) | Zeek integration and reference capture |

---

### Project Outcome

**A packet capture becomes a persistent, evidence-based investigation:** extracted JA4+ fingerprints, linked network activity, explainable rule findings, and a fresh explanation from a genuinely fine-tuned Meta Llama model.
