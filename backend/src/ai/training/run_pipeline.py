"""Launcher orchestration; training starts only via this explicit terminal command."""
import subprocess
import sys
from pathlib import Path
from src.ai.common import ROOT, digest, load_json, now, save_json
from src.ai.training.train_qlora import arguments


def main():
    args = arguments()
    training_options = ['--config', args.config, '--dataset', args.dataset, '--run-dir', args.run_dir,
                        '--max-steps', str(args.max_steps), '--max-runtime', str(args.max_runtime)]
    stamp_path = ROOT / 'results' / 'smoke_test.json'
    smoke_ready = False
    if stamp_path.exists() and (Path(args.dataset) / 'provenance.json').exists():
        stamp = load_json(stamp_path)
        smoke_ready = (stamp.get('passed') and stamp.get('config_hash') == digest(load_json(args.config))
            and stamp.get('dataset_hash') == load_json(Path(args.dataset) / 'provenance.json')['dataset_hash']
            and bool(stamp.get('checkpoint_paths')) and all(Path(p).exists() for p in stamp['checkpoint_paths']))
    commands = [
        *([['src.ai.datasets.prepare', '--output', args.dataset]]
          if not all((Path(args.dataset) / (s + '.jsonl')).exists() and (Path(args.dataset) / (s + '.jsonl')).stat().st_size for s in ('train', 'validation', 'test')) else []),
        ['src.ai.evaluation.evaluate', '--stage', 'before'],
        ['src.ai.training.preflight', '--require-cuda'],
        *([] if smoke_ready else [['src.ai.training.smoke_test', '--config', args.config, '--dataset', args.dataset]]),
        ['src.ai.training.train_qlora', *training_options, *(['--resume', args.resume] if args.resume else [])],
        ['src.ai.evaluation.evaluate', '--stage', 'after', '--adapter', str(Path(args.run_dir) / 'adapter')],
        ['src.ai.evaluation.compare_models'],
    ]
    try:
        for command in commands:
            # Separate processes release VRAM between baseline, smoke, training and evaluation.
            subprocess.run([sys.executable, '-m', *command], check=True)
    except subprocess.CalledProcessError as error:
        save_json(ROOT / 'results' / 'pipeline_failure.json', dict(timestamp=now(), stage=error.cmd[2:], exit_code=error.returncode))
        raise SystemExit(error.returncode)
    save_json(ROOT / 'results' / 'pipeline_status.json', dict(status='completed', timestamp=now(),
        run_dir=args.run_dir, config_hash=digest(load_json(args.config)),
        dataset_hash=load_json(Path(args.dataset) / 'provenance.json')['dataset_hash']))


if __name__ == '__main__':
    main()
