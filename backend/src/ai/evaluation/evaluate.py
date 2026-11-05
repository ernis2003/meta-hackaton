import argparse
from pathlib import Path

from src.ai.common import MODEL_ID, ROOT, digest, load_json, now, save_json
from src.ai.llm.prompts import SYSTEM_PROMPT
from src.ai.llm.schemas import Investigation, parse_response

SETTINGS = dict(do_sample=False, max_new_tokens=768, seed=42, context_limit=4096)


def protocol():
    return dict(cases=load_json(ROOT / 'evaluation' / 'control_questions.json'),
                system_prompt=SYSTEM_PROMPT, output_schema=Investigation.model_json_schema(), settings=SETTINGS)


def evaluate(stage, adapter=None):
    from src.ai.llm.transformers_engine import TransformersEngine
    import torch
    torch.manual_seed(SETTINGS['seed'])
    configuration = protocol()
    fingerprint = digest(configuration)
    before_path = ROOT / 'results' / 'before_training.json'
    if stage == 'after' and not adapter:
        raise ValueError('Post-training evaluation requires an explicit trained adapter')
    if stage == 'after':
        before = load_json(before_path)
        if not before['complete'] or before['protocol_hash'] != fingerprint:
            raise RuntimeError('Baseline incomplete or fixed questions/prompt/settings changed')
        revision = before['model_version']
    else:
        revision = 'main'
    output = ROOT / 'results' / f'{stage}_training.json'
    existing = None
    if output.exists():
        existing = load_json(output)
        if existing['protocol_hash'] != fingerprint:
            raise RuntimeError('Refusing to overwrite evaluation after protocol changes')
        if existing['complete']:
            if stage == 'after' and existing['adapter_identifier'] != digest(load_json(Path(adapter) / 'training_manifest.json')):
                raise RuntimeError('Existing post-training evaluation belongs to a different adapter; archive results explicitly')
            print('Completed evaluation exists; preserving it:', output)
            return existing
        revision = existing['model_version']
    engine = TransformersEngine(revision=revision, adapter=adapter)
    if stage == 'after' and engine.revision != before['model_version']:
        raise RuntimeError('Adapter base revision differs from the baseline')
    result = existing or dict(stage=stage, complete=False, timestamp=now(), model_identifier=MODEL_ID,
                  model_version=engine.revision, adapter_identifier=engine.adapter,
                  protocol_hash=fingerprint, protocol=configuration, responses=[])
    if result['adapter_identifier'] != engine.adapter:
        raise RuntimeError('Partial evaluation belongs to a different adapter')
    completed_ids = {response['test_id'] for response in result['responses']}
    for case in configuration['cases']:
        if case['id'] in completed_ids:
            continue
        generated = engine.generate(case['network_evidence'], case['question'], SETTINGS['max_new_tokens'])
        try:
            parsed = parse_response(generated['raw_response']).model_dump()
            parse_error = None
        except ValueError as error:
            parsed = None
            parse_error = str(error)
        result['responses'].append(dict(test_id=case['id'], question=case['question'],
            network_evidence=case['network_evidence'], **generated, parsed_json=parsed, parse_error=parse_error))
        save_json(output, result)
        print(stage, case['id'], 'JSON valid:', parsed is not None, flush=True)
    result['complete'] = True
    save_json(output, result)
    markdown = [f'# {stage.title()} training evaluation', f'Model: {MODEL_ID} @ {engine.revision}',
                f'Protocol hash: {fingerprint}', 'These are authored held-out scenarios, not PCAP findings.']
    for response in result['responses']:
        markdown.extend([f"## {response['test_id']}", response['question'],
                         '```json\n' + response['raw_response'] + '\n```',
                         f"Duration: {response['duration_seconds']:.3f}s; JSON valid: {response['parsed_json'] is not None}"])
    output.with_suffix('.md').write_text('\n\n'.join(markdown), encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', choices=['before', 'after'], required=True)
    parser.add_argument('--adapter')
    args = parser.parse_args()
    evaluate(args.stage, args.adapter)


if __name__ == '__main__':
    main()
