import httpx
from src.ai.common import MODEL_ID, ROOT, now, save_json
from src.ai.datasets.prepare import auth_headers


def main():
    headers = auth_headers()
    print('Local HF credential available:', bool(headers), flush=True)
    result = dict(timestamp=now(), credential_available=bool(headers))
    for name, url in [('account', 'https://huggingface.co/api/whoami-v2'),
                      ('model', 'https://huggingface.co/' + MODEL_ID + '/resolve/main/config.json')]:
        try:
            response = httpx.get(url, headers=headers, follow_redirects=True, timeout=15)
            result[name + '_status'] = response.status_code
            print(name, response.status_code, flush=True)
            if name == 'model' and response.status_code != 200:
                result['model_error'] = response.text[:1500]
                print(result['model_error'], flush=True)
        except httpx.HTTPError as error:
            result[name + '_error'] = type(error).__name__
            print(name, type(error).__name__, flush=True)
    save_json(ROOT / 'results' / 'access_check.json', result)


if __name__ == '__main__':
    main()
