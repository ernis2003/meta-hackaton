FROM zeek/zeek@sha256:524cb0ce29f26a6a954fb9c357a8f92b95812476d8240f0ece26617ace249dd0

# Official script-only implementation; pin source rather than tracking a moving branch.
ARG JA4_REVISION=8bf9feca52790ae8c926c6a8d79a3547ac19541a
LABEL org.opencontainers.image.source="https://github.com/FoxIO-LLC/ja4-zeek-scripts"
LABEL org.opencontainers.image.revision="8bf9feca52790ae8c926c6a8d79a3547ac19541a"

COPY install_ja4.py /tmp/install_ja4.py
RUN JA4_REVISION=${JA4_REVISION} python3 /tmp/install_ja4.py
