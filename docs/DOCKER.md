# Docker setup

Requires Docker Engine/Desktop with Compose v2 and Linux containers. Windows
users should enable the WSL2 backend in Docker Desktop. Run commands from the
repository root.

## Start the application

```powershell
docker compose up --build -d
docker compose ps
```

Open **http://localhost:8080**. Register a regular account through Sign up.
API documentation is available at http://localhost:8080/docs.

The first build downloads packages, the pinned FoxIO JA4 implementation and its
checksum-verified 90 KB reference capture. Later builds reuse the image cache.
The ordinary application does not require a GPU, Python or Node on the host.

Services:

- `frontend`: production React build, served by unprivileged Nginx. Requests to
  `/api` are proxied to FastAPI on the same origin. SPA routes survive refresh.
- `backend`: FastAPI and native Zeek with JA4/JA4S/JA4H enabled. It runs as a
  non-root user with a single worker, without access to the host Docker socket.
- `inference`: optional NVIDIA GPU service for the actual trained Llama adapter.

The default stack supports upload, JA4 extraction, graph, rule findings, history,
profiles and account administration. Llama explanation requests need either the
GPU profile or a configured external local inference service. Muse additionally
requires the user's own API credentials.

## Persistent storage and credentials

SQLite and an automatically generated private JWT signing key are stored in the
named `forensic_data` volume. Restarting containers preserves accounts, reports
and sessions until token expiry. No shared administrator password is embedded.
Back up the entire volume privately, including its signing key.

The stack does not mount or alter `backend/.env`, the existing host SQLite file,
PCAP datasets or trained weights. Docker accounts/history start in a separate
database. Only the upstream reference capture is included in the backend image;
upload local captures through the interface.

For optional settings:

```powershell
Copy-Item .env.example .env
```

Edit the **root** `.env`, not `backend/.env`. You can change `APP_PORT`, supply
your own `JWT_SECRET_KEY` of at least 32 bytes, configure a new initial admin or
add Muse credentials. Never commit `.env`. `docker compose config` can print
resolved secrets; use `docker compose config --quiet` for validation.

To grant administrator access after registering an account:

```powershell
docker compose exec backend python manage.py make-admin your-email@example.com
```

Sign out and use the Admin login tab. Alternatively, set both `ADMIN_EMAIL` and
`ADMIN_PASSWORD` before first startup. Existing accounts/passwords are not reset
by seeding. Do not reuse public example passwords.

## Fine-tuned Llama with an NVIDIA GPU

Requires an NVIDIA GPU/driver with sufficient VRAM, Docker GPU support (NVIDIA
Container Toolkit on Linux), approved access to
`meta-llama/Llama-3.2-3B-Instruct`, and the actual completed adapter. Neither base
weights nor adapter weights are distributed through Git or baked into an image.

Set in root `.env`:

```dotenv
LLAMA_ADAPTER_PATH=./backend/src/ai/checkpoints/train/adapter
HF_TOKEN=your_own_hugging_face_token
```

The adapter directory must contain the completed `training_manifest.json`,
`adapter_model.safetensors`, adapter config and tokenizer files. A missing bind
source fails rather than creating a fake adapter directory.

```powershell
docker compose --profile gpu up --build -d
docker compose --profile gpu ps
docker compose --profile gpu logs -f inference
```

This explicitly builds the CUDA/PyTorch inference image and may download several
gigabytes. It does **not** train a model. The service verifies the adapter's base,
completion flag and checksum before loading. The backend requires fine-tuned
responses. Wait for `inference` to become healthy before generating explanations.

Hugging Face files default to a persistent `huggingface_cache` volume. To reuse
an existing cache and prevent network downloads, set for example:

```dotenv
HF_CACHE_PATH=C:/Users/your-user/.cache/huggingface
HF_HUB_OFFLINE=1
```

Use an absolute Linux path on Linux. The mounted directory must be readable by
container UID 10001 and contain the pinned base revision from the adapter
manifest. A new writable cache must also permit writes by that user.

### Reuse a model service already running on the host

Instead of starting a second model instance, set:

```dotenv
AI_SERVICE_URL=http://host.docker.internal:8002
```

Then start ordinary `docker compose up --build -d`. On Linux the host service
must listen on an interface reachable from the Docker bridge; a service bound
only to host loopback may not be reachable. Do not expose the inference service
publicly. The backend checks that it reports the required model and fine-tuning.

## Useful commands

```powershell
docker compose logs -f backend frontend
docker compose restart backend
docker compose down
```

`down` preserves named volumes. Avoid `down -v` unless you deliberately intend
to erase Docker accounts, analyses, reports and cached base-model downloads.
For production hosting, put HTTPS in front of Nginx and review host access;
the default published port is bound to localhost.

## Verification scope

Both default and GPU-profile Compose configurations are validated. The core
images were built and tested on 2026-11-05 in an isolated Compose project:

- Both containers became healthy; React production build, SPA deep links,
  registration and proxied API documentation succeeded.
- The included genuine FoxIO capture produced 33 connections and 8 unique
  fingerprints across JA4, JA4S and JA4H. Graph retrieval succeeded.
- A multipart upload of the existing local mixed capture produced 168
  connections and 12 rule findings.
- The container backend reached the existing host inference service and obtained
  a fresh fine-tuned `meta-llama/Llama-3.2-3B-Instruct` explanation in 14.33 seconds.
  Saved explanation retrieval and two-entry Analysis History succeeded.
- Restarting the backend preserved its account, JWT session, both analyses and
  saved explanation. Backend UID was 10001 and the generated key had mode 0600.
  No private `.env`, adapter or Docker socket was present in the backend.

The GPU image is an optional deployment recipe; its CUDA build and containerized model load
must be verified on the destination GPU machine. It is not a claim that model
weights are bundled or that every machine can run inference.

References: [Docker GPU support](https://docs.docker.com/compose/how-tos/gpu-support/),
[Compose profiles](https://docs.docker.com/compose/how-tos/profiles/),
[Nginx proxy behavior](https://nginx.org/en/docs/http/ngx_http_proxy_module.html).
