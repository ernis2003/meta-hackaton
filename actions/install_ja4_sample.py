"""Download an unchanged, checksum-pinned upstream capture; never generate traffic."""
from hashlib import sha256
from pathlib import Path
from urllib.request import urlopen

REVISION = 'c6469a7b0dbf8fe963810162429fbfd9d1acc4d5'
URL = f'https://raw.githubusercontent.com/FoxIO-LLC/ja4/{REVISION}/pcap/latest.pcapng'
SHA256 = '15973185fd81b88837fcbe396eb66f437d0a68a2b5ccfa1e5ed0c6b2a15bfa7c'
TARGET = Path(__file__).resolve().parents[1] / 'backend/src/data/pcap_samples/foxio-latest.pcapng'


def main():
    if TARGET.exists():
        content = TARGET.read_bytes()
    else:
        with urlopen(URL, timeout=30) as response:
            content = response.read(1024 * 1024)
    if sha256(content).hexdigest() != SHA256:
        raise RuntimeError('Upstream sample checksum mismatch; preserving existing files')
    if not TARGET.exists():
        TARGET.parent.mkdir(parents=True, exist_ok=True)
        TARGET.write_bytes(content)
    print('Verified official FoxIO capture:', TARGET.name)


if __name__ == '__main__':
    main()
