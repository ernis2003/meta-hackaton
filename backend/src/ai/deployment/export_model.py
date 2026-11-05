"""Explicit merge/export. Never assume an NF4 PEFT adapter imports into Ollama."""
import argparse
import subprocess
from pathlib import Path
import httpx
from src.ai.common import MODEL_ID, digest, file_digest, load_json, save_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--adapter', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--ollama-name', default='ja4-investigator')
    parser.add_argument('--import-ollama', action='store_true')
    args = parser.parse_args()
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer
    manifest = load_json(Path(args.adapter) / 'training_manifest.json')
    if manifest['model'] != MODEL_ID or not manifest['completed'] or manifest['smoke']:
        raise ValueError('A completed full-training adapter is required')
    if manifest['adapter_sha256'] != file_digest(Path(args.adapter) / 'adapter_model.safetensors'):
        raise ValueError('Adapter weight hash differs from its manifest')
    if Path(args.output).resolve() == Path(args.adapter).resolve():
        raise ValueError('Merged output must be separate from the original adapter')
    # Export may run in system RAM to avoid needing both FP16 base + merged copy in 8 GiB VRAM.
    # This is export, never CPU training or silent application inference fallback.
    base = AutoModelForCausalLM.from_pretrained(MODEL_ID, revision=manifest['model_revision'],
        torch_dtype=torch.float16, device_map={'': 'cpu'}, trust_remote_code=False, use_safetensors=True)
    merged = PeftModel.from_pretrained(base, args.adapter).merge_and_unload(safe_merge=True)
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(output, safe_serialization=True, max_shard_size='2GB')
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, revision=manifest['model_revision'])
    tokenizer.save_pretrained(output)
    deployment = dict(model=MODEL_ID, model_revision=manifest['model_revision'], adapter_identifier=digest(manifest),
                      ollama_model=args.ollama_name, ollama_digest=None)
    modelfile = output / 'Modelfile'
    modelfile.write_text('FROM "' + str(output).replace('\\', '/') + '"\nPARAMETER temperature 0\nPARAMETER num_ctx 4096\n', encoding='utf-8')
    if args.import_ollama:
        subprocess.run(['ollama', 'create', args.ollama_name, '-f', str(modelfile), '--quantize', 'q4_K_M'], check=True)
        response = httpx.get('http://127.0.0.1:11434/api/tags', timeout=15)
        response.raise_for_status()
        installed = next(m for m in response.json()['models'] if m['name'] in (args.ollama_name, args.ollama_name + ':latest'))
        deployment['ollama_model'] = installed['name']
        deployment['ollama_digest'] = installed['digest']
    save_json(output / 'deployment_manifest.json', deployment)
    print('Export saved. If Ollama import fails, use the Transformers+PEFT local service with the original adapter.')


if __name__ == '__main__':
    main()
