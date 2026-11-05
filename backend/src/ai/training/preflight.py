import argparse
import importlib.metadata
import importlib.util
import platform
import shutil
import subprocess
import sys

from src.ai.common import MODEL_ID, ROOT, now, save_json


def inspect(require_cuda=False):
    result = dict(timestamp=now(), python=sys.version, platform=platform.platform(),
                  disk_free_gib=round(shutil.disk_usage(ROOT).free / 2**30, 2), dependencies={}, errors=[])
    for package in ('torch', 'transformers', 'peft', 'trl', 'accelerate', 'bitsandbytes', 'datasets', 'safetensors'):
        try:
            result['dependencies'][package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            result['dependencies'][package] = None
            result['errors'].append(f'Missing dependency: {package}')
    try:
        import psutil
        result['ram'] = dict(total_gib=psutil.virtual_memory().total / 2**30,
                             available_gib=psutil.virtual_memory().available / 2**30)
    except ImportError:
        result['ram'] = None
    try:
        command = subprocess.run(['nvidia-smi', '--query-gpu=name,driver_version,memory.total,memory.free,utilization.gpu',
                                  '--format=csv,noheader'], capture_output=True, text=True, timeout=10)
        result['nvidia_smi'] = command.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        result['nvidia_smi'] = None
    try:
        import torch
        result['cuda_available'] = torch.cuda.is_available()
        result['torch_cuda_version'] = torch.version.cuda
        if not torch.cuda.is_available():
            result['errors'].append('CUDA unavailable; CPU training is disabled')
        else:
            result['gpu_name'] = torch.cuda.get_device_name(0)
            result['compute_capability'] = torch.cuda.get_device_capability(0)
            # Execute a kernel; driver detection alone does not prove Blackwell support.
            x = torch.randn(128, 128, device='cuda', requires_grad=True)
            (x @ x).sum().backward()
            torch.cuda.synchronize()
            result['cuda_kernel_test'] = 'passed'
    except Exception as error:
        result['errors'].append(f'CUDA kernel check failed: {type(error).__name__}: {error}')
    try:
        from huggingface_hub import hf_hub_download
        path = hf_hub_download(MODEL_ID, 'config.json')
        result['model_config_access'] = bool(path)
    except Exception as error:
        result['model_config_access'] = False
        result['errors'].append(f'Model access unavailable ({type(error).__name__}); accept Meta terms and run hf auth login')
    save_json(ROOT / 'results' / 'preflight.json', result)
    if require_cuda and (not result.get('cuda_available') or result.get('cuda_kernel_test') != 'passed'):
        raise RuntimeError('CUDA preflight failed; see results/preflight.json. No CPU fallback.')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--require-cuda', action='store_true')
    args = parser.parse_args()
    import json
    result = inspect(args.require_cuda)
    print(json.dumps(result, indent=2))
    if result['errors']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
