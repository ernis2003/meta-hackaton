"""GPU-only official model loader shared by evaluation and the optional service."""
import time
import re
from pathlib import Path

from src.ai.common import MODEL_ID, digest, file_digest, load_json, now
from src.ai.llm.prompts import messages


class TransformersEngine:
    def __init__(self, revision='main', adapter=None):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        from huggingface_hub import model_info, snapshot_download
        from huggingface_hub.errors import LocalEntryNotFoundError
        if not torch.cuda.is_available():
            raise RuntimeError('CUDA is required; CPU fallback is disabled')
        self.adapter = None
        if adapter:
            manifest = load_json(Path(adapter) / 'training_manifest.json')
            if manifest['model'] != MODEL_ID or not manifest.get('completed') or manifest.get('smoke'):
                raise RuntimeError('Adapter is not a completed training run for the official model')
            if manifest.get('adapter_sha256') != file_digest(Path(adapter) / 'adapter_model.safetensors'):
                raise RuntimeError('Adapter weights do not match the training manifest')
            revision = manifest['model_revision']
            self.adapter = digest(manifest)
        # Completed adapters already pin an immutable revision. Reuse the local
        # snapshot so restarting inference does not require Hugging Face access.
        self.revision = revision if re.fullmatch(r'[0-9a-f]{40}', revision) else model_info(MODEL_ID, revision=revision).sha
        try:
            model_source = snapshot_download(MODEL_ID, revision=self.revision, local_files_only=True)
        except LocalEntryNotFoundError:
            model_source = MODEL_ID
        self.dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
        self.tokenizer = AutoTokenizer.from_pretrained(model_source, revision=self.revision, trust_remote_code=False)
        self.tokenizer.pad_token = self.tokenizer.eos_token
        self.model = AutoModelForCausalLM.from_pretrained(model_source, revision=self.revision,
            quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=self.dtype),
            device_map={'': 0}, torch_dtype=self.dtype, trust_remote_code=False, use_safetensors=True)
        if adapter:
            from peft import PeftModel
            self.model = PeftModel.from_pretrained(self.model, adapter, is_trainable=False)
        if any(p.device.type != 'cuda' for p in self.model.parameters()):
            raise RuntimeError('Model placement includes non-CUDA parameters; refusing CPU offload')
        self.model.eval()

    def generate(self, evidence, question=None, max_new_tokens=768):
        import torch
        start = time.monotonic()
        conversation = messages(evidence, question) if question else messages(evidence)
        prompt = self.tokenizer.apply_chat_template(conversation, tokenize=False, add_generation_prompt=True)
        inputs = self.tokenizer(prompt, return_tensors='pt').to('cuda')
        # Never silently truncate authoritative evidence or the output schema.
        if inputs.input_ids.shape[-1] > 3072:
            raise ValueError('Evidence exceeds the inference input budget; reduce the evidence explicitly')
        with torch.inference_mode():
            output = self.model.generate(**inputs, max_new_tokens=max_new_tokens,
                do_sample=False, pad_token_id=self.tokenizer.eos_token_id)
        raw = self.tokenizer.decode(output[0, inputs.input_ids.shape[-1]:], skip_special_tokens=True)
        return dict(raw_response=raw, duration_seconds=time.monotonic() - start,
                    model_identifier=MODEL_ID, model_version=self.revision,
                    adapter_identifier=self.adapter, fine_tuned=bool(self.adapter), generated_at=now())
