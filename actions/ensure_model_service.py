"""Ensure the configured local Transformers service is ready before starting the API."""
import os
from pathlib import Path
import subprocess
import time
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parents[1] / 'backend'


def main():
    load_dotenv(BACKEND / '.env')
    if os.getenv('AI_RUNTIME', 'ollama') != 'transformers':
        return 0
    endpoint = os.getenv('AI_SERVICE_URL', 'http://127.0.0.1:8002').rstrip('/')
    require_adapter = os.getenv('AI_REQUIRE_FINE_TUNED', 'false').lower() == 'true'

    def ready():
        try:
            response = httpx.get(endpoint + '/health', timeout=2)
            response.raise_for_status()
            health = response.json()
            return (health.get('model_identifier') == 'meta-llama/Llama-3.2-3B-Instruct'
                    and (not require_adapter or health.get('fine_tuned') is True))
        except (httpx.HTTPError, ValueError):
            return False

    if ready():
        print('Local Llama service is ready.', flush=True)
        return 0
    address = urlparse(endpoint)
    if address.hostname not in ('127.0.0.1', 'localhost') or address.scheme != 'http':
        print(f'Configured service is unavailable: {endpoint}', flush=True)
        return 1
    python = BACKEND / '.venv-ai' / 'Scripts' / 'python.exe'
    if not python.is_file():
        print(f'AI Python environment is missing: {python}', flush=True)
        return 1
    log = BACKEND / 'src' / 'ai' / 'results' / 'model_service.log'
    log.parent.mkdir(parents=True, exist_ok=True)
    print(f'Starting local Llama at {endpoint}. Loading may take several minutes. Log: {log}', flush=True)
    with log.open('a', encoding='utf-8') as output:
        process = subprocess.Popen(
            [str(python), '-m', 'uvicorn', 'src.ai.llm.server:app',
             '--host', address.hostname, '--port', str(address.port or 80)],
            cwd=BACKEND, stdout=output, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        if process.poll() is not None:
            print(f'Model service exited ({process.returncode}). See {log}', flush=True)
            return 1
        if ready():
            print('Local Llama service is ready.', flush=True)
            return 0
        time.sleep(2)
    process.terminate()
    print(f'Model service did not become ready within 10 minutes. See {log}', flush=True)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
