"""Install the checksum-pinned upstream revision into the Zeek image."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

REVISION = os.getenv('JA4_REVISION', '8bf9feca52790ae8c926c6a8d79a3547ac19541a')
DESTINATION = Path('/usr/local/zeek/share/zeek/site/ja4')


def main():
    with tempfile.TemporaryDirectory(prefix='ja4-source-') as temporary:
        source = Path(temporary)
        commands = [
            ['git', 'init', str(source)],
            ['git', '-C', str(source), 'remote', 'add', 'origin',
             'https://github.com/FoxIO-LLC/ja4-zeek-scripts.git'],
            ['git', '-C', str(source), 'fetch', '--depth', '1', '--filter=blob:none', 'origin', REVISION],
            ['git', '-C', str(source), 'sparse-checkout', 'init', '--cone'],
            ['git', '-C', str(source), 'sparse-checkout', 'set', 'zeek'],
            ['git', '-C', str(source), 'checkout', '--detach', 'FETCH_HEAD'],
        ]
        for command in commands:
            subprocess.run(command, check=True)
        shutil.copytree(source / 'zeek', DESTINATION)
        documentation = Path('/usr/local/share/doc/ja4')
        documentation.mkdir(parents=True, exist_ok=True)
        for item in source.iterdir():
            if item.is_file() and ('license' in item.name.lower() or item.name == 'README.md'):
                shutil.copy2(item, documentation / item.name)
    probe = subprocess.run(['zeek', 'ja4', '-e',
                            'print record_fields(SSL::Info); print record_fields(HTTP::Info);'],
                           capture_output=True, text=True, check=True)
    for kind in ('ja4', 'ja4s', 'ja4h'):
        if not re.search(r'\[' + kind + r'\]', probe.stdout, re.I):
            raise RuntimeError('Missing Zeek fingerprint field: ' + kind)
    print('Verified JA4, JA4S and JA4H fields at upstream revision', REVISION)


if __name__ == '__main__':
    main()
