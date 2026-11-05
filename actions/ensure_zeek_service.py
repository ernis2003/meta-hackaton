"""Ensure Docker is available for the configured Zeek runtime."""
import os
from pathlib import Path
import subprocess
import time
from dotenv import load_dotenv


def main():
    load_dotenv(Path(__file__).resolve().parents[1] / 'backend/.env')
    if os.getenv('ZEEK_MODE', 'docker' if os.name == 'nt' else 'native') != 'docker':
        return 0

    def ready():
        try:
            return subprocess.run(['docker', 'info'], capture_output=True, timeout=10).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    if not ready():
        desktop = Path(os.getenv('ProgramFiles', 'C:/Program Files')) / 'Docker/Docker/Docker Desktop.exe'
        if os.name != 'nt' or not desktop.is_file():
            print('Docker is unavailable. Install/start Docker Desktop before starting the backend.', flush=True)
            return 1
        print('Starting Docker Desktop for Zeek; waiting for its engine...', flush=True)
        subprocess.Popen([str(desktop)], creationflags=subprocess.CREATE_NO_WINDOW)
        deadline = time.monotonic() + 180
        while not ready():
            if time.monotonic() >= deadline:
                print('Docker did not become ready. Check its engine status in Docker Desktop.', flush=True)
                return 1
            time.sleep(2)
    image = os.getenv('ZEEK_DOCKER_IMAGE', 'zeek/zeek:latest')
    if subprocess.run(['docker', 'image', 'inspect', image], capture_output=True).returncode:
        instruction = ('actions\\build_zeek_ja4_windows.bat' if image == 'forensics-zeek-ja4:local'
                       else f'docker pull {image}')
        print(f'Zeek image is missing. Run from the repository root: {instruction}', flush=True)
        return 1
    print('Docker is ready for Zeek.', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
