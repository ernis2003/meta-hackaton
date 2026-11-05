"""Explicit CUDA-only adapter training; never imported or launched by FastAPI."""
import argparse
import json
import time
from pathlib import Path

from src.ai.common import MODEL_ID, ROOT, digest, file_digest, load_json, now, read_jsonl, save_json
from src.ai.training.preflight import inspect


def summarize_run(output):
    """Keep actual optimizer-run metrics separate from zero-update finalization resumes."""
    entries = read_jsonl(Path(output) / 'training_log.jsonl')
    runs = [entry for entry in entries if 'train_runtime' in entry]
    if not runs:
        raise ValueError('No completed training metrics were recorded')
    optimizer_run = max(runs, key=lambda entry: entry['train_runtime'])
    validations = [entry for entry in entries if 'eval_loss' in entry]
    tests = [entry for entry in entries if 'test_loss' in entry]
    summary = dict(model_identifier=MODEL_ID, global_step=optimizer_run['global_step'],
        completed_epochs=optimizer_run['epoch'], training_loss=optimizer_run['train_loss'],
        training_runtime_seconds=optimizer_run['train_runtime'],
        peak_vram_bytes=max(entry.get('peak_vram_bytes', 0) for entry in entries),
        validation_loss=validations[-1]['eval_loss'] if validations else None,
        test_loss=tests[-1]['test_loss'] if tests else None,
        finalization_resumes=sum(entry['train_runtime'] < 1 for entry in runs))
    save_json(Path(output) / 'training_metrics.json', summary)
    return summary


def train(args, smoke=False):
    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import TrainerCallback
    from transformers.trainer_utils import get_last_checkpoint
    from trl import SFTConfig, SFTTrainer
    from src.ai.evaluation.evaluate import protocol
    from src.ai.llm.transformers_engine import TransformersEngine

    config = load_json(args.config)
    if config['model'] != MODEL_ID:
        raise ValueError('Only the requested official Meta Llama 3.2 3B model is supported')
    inspect(require_cuda=True)
    dataset_dir = Path(args.dataset)
    provenance = load_json(dataset_dir / 'provenance.json')
    stored_splits = {name: read_jsonl(dataset_dir / (name + '.jsonl')) for name in ('validation', 'test', 'train')}
    if digest([row for name in ('validation', 'test', 'train') for row in stored_splits[name]]) != provenance['dataset_hash']:
        raise ValueError('Prepared files no longer match the recorded dataset hash')
    identifiers = [row['id'] for rows in stored_splits.values() for row in rows]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError('Duplicate prompts across prepared splits')
    if provenance['controls_hash'] != digest(protocol()['cases']):
        raise ValueError('Dataset was prepared against a different held-out evaluation set')
    if not smoke:
        before = load_json(ROOT / 'results' / 'before_training.json')
        stamp = load_json(ROOT / 'results' / 'smoke_test.json')
        if not before['complete'] or before['protocol_hash'] != digest(protocol()):
            raise ValueError('Complete and unchanged baseline evaluation is required before full training')
        if not stamp['passed'] or stamp['config_hash'] != digest(config) or stamp['dataset_hash'] != provenance['dataset_hash']:
            raise ValueError('Run a successful GPU smoke test with the same configuration and dataset first')
        revision = before['model_version']
        if stamp['model_revision'] != revision:
            raise ValueError('Smoke test model revision differs from the baseline')
    else:
        baseline = ROOT / 'results' / 'before_training.json'
        revision = load_json(baseline)['model_version'] if baseline.exists() else config['revision']
    engine = TransformersEngine(revision=revision)
    model = prepare_model_for_kbit_training(engine.model, use_gradient_checkpointing=True)
    model.config.use_cache = False
    lora = config['lora']
    model = get_peft_model(model, LoraConfig(r=lora['r'], lora_alpha=lora['alpha'],
        lora_dropout=lora['dropout'], target_modules=lora['target_modules'], bias='none', task_type='CAUSAL_LM'))
    trainable = [name for name, p in model.named_parameters() if p.requires_grad]
    if not trainable or any('lora_' not in name for name in trainable):
        raise RuntimeError('Only LoRA parameters may be trainable; base model must remain frozen')
    if any(p.device.type != 'cuda' for p in model.parameters()):
        raise RuntimeError('CPU/offloaded parameters are not allowed')
    settings = config['training']
    tokenizer = engine.tokenizer
    rejected = {}

    def dataset(split):
        result = []
        rows = stored_splits[split]
        for row in rows:
            conversation = row['messages']
            prompt = tokenizer.apply_chat_template(conversation[:-1], tokenize=False, add_generation_prompt=True)
            entire = tokenizer.apply_chat_template(conversation, tokenize=False)
            if not entire.startswith(prompt):
                continue
            if len(tokenizer(entire).input_ids) > settings['max_seq_length']:
                continue  # Do not truncate away targets or train on an incomplete assistant answer.
            result.append(dict(prompt=prompt, completion=entire[len(prompt):]))
        rejected[split] = dict(input=len(rows), retained=len(result), rejected=len(rows) - len(result))
        if not result:
            raise ValueError(f'No {split} records fit max_seq_length; inspect preparation and lengths')
        return Dataset.from_list(result)

    train_data, validation = dataset('train'), dataset('validation')
    if smoke:
        train_data = train_data.select(range(min(8, len(train_data))))
        validation = validation.select(range(min(2, len(validation))))
    output = Path(args.run_dir) if not smoke else ROOT / 'checkpoints' / 'smoke' / digest(config)[:12]
    output.mkdir(parents=True, exist_ok=True)
    identity = dict(config_hash=digest(config), dataset_hash=provenance['dataset_hash'], model_revision=engine.revision)
    identity_path = output / 'run_identity.json'
    if identity_path.exists() and load_json(identity_path) != identity:
        raise ValueError('Existing run has a different model/configuration/dataset; choose a new --run-dir')
    save_json(identity_path, identity)
    if not smoke and (output / 'adapter' / 'training_manifest.json').exists() and not args.resume:
        raise ValueError('Adapter already exists; use a new --run-dir or explicit --resume')
    start = time.monotonic()
    torch.cuda.reset_peak_memory_stats()

    class LogProgress(TrainerCallback):
        timed_out = False

        def on_log(self, arguments, state, control, logs=None, **kwargs):
            entry = dict(logs or {}, global_step=state.global_step, epoch=state.epoch,
                         elapsed_seconds=time.monotonic() - start,
                         gpu_memory_allocated=torch.cuda.memory_allocated(),
                         peak_vram_bytes=torch.cuda.max_memory_allocated())
            try:
                import subprocess
                gpu = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu,memory.used', '--format=csv,noheader,nounits'],
                                     capture_output=True, text=True, timeout=5)
                entry['gpu_utilization_and_memory_mib'] = gpu.stdout.strip()
            except (OSError, subprocess.TimeoutExpired):
                pass
            with (output / 'training_log.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(entry) + '\n')

        def on_step_end(self, arguments, state, control, **kwargs):
            if args.max_runtime and time.monotonic() - start >= args.max_runtime:
                self.timed_out = True
                control.should_save = True
                control.should_training_stop = True
            return control

        def on_save(self, arguments, state, control, **kwargs):
            checkpoint = output / f'checkpoint-{state.global_step}'
            self.on_log(arguments, state, control, logs={'checkpoint_path': str(checkpoint), 'checkpoint_exists': checkpoint.exists()})

    callback = LogProgress()
    options = SFTConfig(output_dir=str(output), num_train_epochs=settings['epochs'],
        per_device_train_batch_size=settings['batch_size'], per_device_eval_batch_size=1,
        gradient_accumulation_steps=1 if smoke else settings['gradient_accumulation_steps'],
        learning_rate=settings['learning_rate'], max_length=settings['max_seq_length'],
        gradient_checkpointing=settings['gradient_checkpointing'], gradient_checkpointing_kwargs={'use_reentrant': False},
        bf16=engine.dtype == torch.bfloat16, fp16=engine.dtype == torch.float16,
        seed=settings['seed'], max_steps=2 if smoke else args.max_steps,
        logging_steps=1, eval_strategy='steps' if smoke else 'epoch', eval_steps=2 if smoke else None,
        save_strategy='steps', save_steps=1 if smoke else 25, save_total_limit=None,
        report_to='none', optim='paged_adamw_8bit', completion_only_loss=True,
        packing=False, dataloader_num_workers=0, save_safetensors=True)
    trainer = SFTTrainer(model=model, args=options, train_dataset=train_data,
                         eval_dataset=validation, processing_class=tokenizer, callbacks=[callback])
    resume = get_last_checkpoint(str(output)) if args.resume == 'latest' else args.resume
    if args.resume and not resume:
        raise ValueError('No checkpoint found to resume')
    try:
        trainer.train(resume_from_checkpoint=resume)
    except (torch.cuda.OutOfMemoryError, KeyboardInterrupt) as error:
        # Adapter is marked interrupted; periodic trainer checkpoints remain resumable.
        try:
            trainer.model.save_pretrained(output / 'interrupted_adapter', safe_serialization=True)
        except Exception:
            pass  # Preserve the original failure; prior periodic checkpoints remain available.
        save_json(output / 'failure.json', dict(error=type(error).__name__, timestamp=now(),
                  peak_vram_bytes=torch.cuda.max_memory_allocated(), fallback='Use config-fallback.json, rerun smoke test, then resume only a matching configuration.'))
        raise
    adapter = output / 'adapter'
    trainer.model.save_pretrained(adapter, safe_serialization=True)
    tokenizer.save_pretrained(adapter)
    test_metrics = None
    if not smoke and not callback.timed_out:
        # Trainer.evaluate does not apply SFTTrainer's initialization-time preprocessing.
        # Prepare held-out targets only now, after the last optimizer update.
        def tokenize_test(row):
            prompt_ids = tokenizer(row['prompt'])['input_ids']
            input_ids = tokenizer(row['prompt'] + row['completion'])['input_ids']
            if input_ids[:len(prompt_ids)] != prompt_ids:
                raise ValueError('Held-out prompt tokenization is not a prefix of the full conversation')
            if len(input_ids) > settings['max_seq_length']:
                raise ValueError('Held-out example exceeds the configured sequence length')
            return dict(input_ids=input_ids,
                        completion_mask=[0] * len(prompt_ids) + [1] * (len(input_ids) - len(prompt_ids)))
        test_data = dataset('test').map(tokenize_test, remove_columns=['prompt', 'completion'])
        test_metrics = trainer.evaluate(eval_dataset=test_data, metric_key_prefix='test')
        save_json(output / 'test_metrics.json', test_metrics)
    manifest = dict(model=MODEL_ID, model_revision=engine.revision, timestamp=now(),
        config=config, config_hash=digest(config), dataset_hash=provenance['dataset_hash'],
        dataset_counts=rejected, global_step=trainer.state.global_step, smoke=smoke,
        elapsed_seconds=time.monotonic() - start, peak_vram_bytes=torch.cuda.max_memory_allocated(),
        trainable_parameter_count=sum(p.numel() for p in model.parameters() if p.requires_grad),
        adapter_sha256=file_digest(adapter / 'adapter_model.safetensors'),
        completed=not callback.timed_out, test_metrics=test_metrics,
        run_metrics=summarize_run(output))
    save_json(adapter / 'training_manifest.json', manifest)
    if smoke:
        checkpoints = list(output.glob('checkpoint-*'))
        passed = bool(checkpoints and (adapter / 'adapter_model.safetensors').exists() and trainer.state.global_step >= 2)
        save_json(ROOT / 'results' / 'smoke_test.json', dict(passed=passed, timestamp=now(),
                  model_revision=engine.revision, config_hash=digest(config), dataset_hash=provenance['dataset_hash'],
                  checkpoint_paths=[str(p) for p in checkpoints], peak_vram_bytes=manifest['peak_vram_bytes']))
        if not passed:
            raise RuntimeError('Smoke test did not save a checkpoint/adapter')
    if callback.timed_out:
        raise RuntimeError('Maximum runtime reached; resumable checkpoint saved, post-training evaluation not run')
    return adapter


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=str(ROOT / 'training' / 'config.json'))
    parser.add_argument('--dataset', default=str(ROOT / 'datasets' / 'prepared'))
    parser.add_argument('--run-dir', default=str(ROOT / 'checkpoints' / 'train'))
    parser.add_argument('--max-steps', type=int, default=-1)
    parser.add_argument('--max-runtime', type=float, default=0, help='Seconds; checked at optimizer step boundaries')
    parser.add_argument('--resume', nargs='?', const='latest')
    return parser.parse_args()


if __name__ == '__main__':
    train(arguments())
