"""Application-side local inference client. No training packages imported here."""
import os
import time
import httpx

from src.ai.common import MODEL_ID, load_json, now
from src.ai.llm.prompts import messages
from src.ai.llm.schemas import Generation, Investigation, parse_response


class ModelUnavailable(RuntimeError):
    pass


def explain_anomaly(anomaly_data: dict) -> dict:
    runtime = os.getenv('AI_RUNTIME', 'ollama')
    start = time.monotonic()
    try:
        if runtime == 'transformers':
            endpoint = os.getenv('AI_SERVICE_URL', 'http://127.0.0.1:8002')
            response = httpx.post(endpoint + '/generate', json={'evidence': anomaly_data}, timeout=180)
            response.raise_for_status()
            result = Generation.model_validate(response.json())
            if result.model_identifier != MODEL_ID:
                raise ModelUnavailable('Inference service is not using the configured official Llama 3.2 3B model')
            if os.getenv('AI_REQUIRE_FINE_TUNED', 'false').lower() == 'true' and not result.fine_tuned:
                raise ModelUnavailable('Fine-tuned inference required; service reports baseline')
            return result.model_dump()
        if runtime != 'ollama':
            raise ModelUnavailable('AI_RUNTIME must be ollama or transformers')
        endpoint = os.getenv('OLLAMA_URL', 'http://127.0.0.1:11434')
        model = os.getenv('OLLAMA_MODEL', 'llama3.2:3b-instruct-q4_K_M')
        tags = httpx.get(endpoint + '/api/tags', timeout=10)
        tags.raise_for_status()
        installed = next((m for m in tags.json().get('models', []) if m['name'] == model), None)
        if not installed:
            raise ModelUnavailable(f'Local model {model} is not installed. Download it with the documented pull command.')
        adapter = None
        if model != 'llama3.2:3b-instruct-q4_K_M':
            manifest_path = os.getenv('AI_DEPLOYMENT_MANIFEST')
            if not manifest_path:
                raise ModelUnavailable('Custom Ollama models require an export deployment manifest')
            manifest = load_json(manifest_path)
            if (manifest.get('model') != MODEL_ID or manifest.get('ollama_model') != model
                    or manifest.get('ollama_digest') != installed['digest'] or not manifest.get('adapter_identifier')):
                raise ModelUnavailable('Ollama model digest does not match the trained deployment manifest')
            adapter = manifest['adapter_identifier']
        if os.getenv('AI_REQUIRE_FINE_TUNED', 'false').lower() == 'true' and not adapter:
            raise ModelUnavailable('Fine-tuned model required; configured model is the baseline')
        response = httpx.post(endpoint + '/api/chat', json={
            'model': model, 'messages': messages(anomaly_data), 'stream': False,
            'format': Investigation.model_json_schema(), 'keep_alive': '5m',
            'options': {'temperature': 0, 'seed': 42, 'num_predict': 768, 'num_ctx': 4096},
        }, timeout=180)
        response.raise_for_status()
        report = parse_response(response.json()['message']['content'])
        return Generation(report=report, model_identifier=MODEL_ID,
                          model_version='ollama:' + installed['digest'], adapter_identifier=adapter,
                          fine_tuned=bool(adapter), generated_at=now(),
                          duration_seconds=time.monotonic() - start).model_dump()
    except ModelUnavailable:
        raise
    except (httpx.HTTPError, OSError) as error:
        raise ModelUnavailable('Local model service unavailable; verify the runtime and model installation') from error
    except (ValueError, KeyError) as error:
        raise ModelUnavailable('Model returned an invalid investigation report; no explanation was saved') from error
