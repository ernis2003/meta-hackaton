"""Start explicitly: .venv-ai Python -m uvicorn src.ai.llm.server:app --port 8002."""
import os
from contextlib import asynccontextmanager
from threading import Lock
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from src.ai.llm.schemas import Generation, parse_response
from src.ai.llm.transformers_engine import TransformersEngine
from dotenv import load_dotenv

load_dotenv()

engine = None
generation_lock = Lock()


@asynccontextmanager
async def lifespan(app):
    global engine
    engine = TransformersEngine(adapter=os.getenv('AI_ADAPTER_PATH') or None)
    yield
    engine = None


app = FastAPI(title='Local Llama Inference', lifespan=lifespan)


class Request(BaseModel):
    evidence: dict


@app.get('/health')
def health():
    from src.ai.common import MODEL_ID
    if not engine:
        raise HTTPException(503, 'Model not loaded')
    return dict(model_identifier=MODEL_ID, model_version=engine.revision,
                adapter_identifier=engine.adapter, fine_tuned=bool(engine.adapter))


@app.post('/generate', response_model=Generation)
def generate(request: Request):
    if not engine:
        raise HTTPException(503, 'Model not loaded')
    if not generation_lock.acquire(blocking=False):
        raise HTTPException(409, 'Model is busy')
    try:
        result = engine.generate(request.evidence, question=(
            'Explain why this anomaly was flagged. In observations, cite the supplied anomaly type, '
            'connection counts, byte totals, interval measurements and detector rule where present. '
            'Separate these recorded facts from hypotheses. Do not claim an independent review occurred. '
            'Give plausible benign alternatives and concrete next investigation steps. '
            'Return only the required JSON fields.'))
        result['report'] = parse_response(result.pop('raw_response'))
        return result
    except Exception:
        raise HTTPException(502, 'Model generation failed or returned invalid JSON') from None
    finally:
        generation_lock.release()
