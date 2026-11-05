# Local JA4+ extraction

From repository root:

```powershell
.\actions\build_zeek_ja4_windows.bat
.\backend\.venv\Scripts\python.exe actions/install_ja4_sample.py
```

Configure the private `backend/.env`, then restart the backend:

```dotenv
ZEEK_MODE=docker
ZEEK_DOCKER_IMAGE=forensics-zeek-ja4:local
ZEEK_SCRIPTS=ja4
```

The image uses the already-tested Zeek 9.0.1 image digest and official
[FoxIO script-only implementation](https://github.com/FoxIO-LLC/ja4-zeek-scripts)
at revision `8bf9feca52790ae8c926c6a8d79a3547ac19541a`.
Source documentation/license files are retained in the image under
`/usr/local/share/doc/ja4`. Observe the upstream FoxIO license when distributing.
Capture processing remains offline in network-disabled containers.

`JA4`, `JA4S` and `JA4H` are confirmed supported by schema inspection and real
capture extraction. A supported method may have zero values when its required
traffic is absent. In particular, the existing normal/suspicious/mixed samples
contain ClientHello messages but no ServerHello, so they do not yield JA4S.

The optional **Analyze JA4+ reference capture** action uses the unmodified
[official capture](https://github.com/FoxIO-LLC/ja4/blob/c6469a7b0dbf8fe963810162429fbfd9d1acc4d5/pcap/latest.pcapng).
SHA256: `15973185fd81b88837fcbe396eb66f437d0a68a2b5ccfa1e5ed0c6b2a15bfa7c`.
Observed results: 33 connections, 3 unique JA4, 4 JA4S and 1 JA4H. Capture bytes
remain ignored by Git; the installer preserves and verifies existing files.
These are upstream reference packets, not asserted safe or malicious traffic.

Reanalysis creates a new owned analysis through the normal API. Old analyses,
AI reports and their original capability metadata are retained. Historical
links remain historical; the fingerprint page can reanalyze installed samples.

Optional integration verification from `backend`:

```powershell
$env:RUN_ZEEK_E2E='1'
$env:RUN_JA4_E2E='1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
