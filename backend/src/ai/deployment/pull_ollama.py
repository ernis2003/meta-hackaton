"""Download the published Llama 3.2 3B baseline from Ollama's official library."""
import httpx


def main():
    with httpx.stream('POST', 'http://127.0.0.1:11434/api/pull',
                      json={'model': 'llama3.2:3b-instruct-q4_K_M', 'stream': True}, timeout=600) as response:
        response.raise_for_status()
        import json
        last = ''
        for line in response.iter_lines():
            if not line:
                continue
            progress = json.loads(line)
            if progress.get('error'):
                raise RuntimeError(progress['error'])
            status = progress.get('status', '')
            if status != last:
                print(status, flush=True)
                last = status


if __name__ == '__main__':
    main()
