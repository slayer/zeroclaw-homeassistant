ARG BUILD_FROM
FROM ${BUILD_FROM}

ARG ZEROCLAW_VERSION=latest

# jq: parse /data/options.json, curl: download binary, ca-certificates: TLS
RUN apt-get update && apt-get install -y --no-install-recommends jq curl ca-certificates && rm -rf /var/lib/apt/lists/*

# Download ZeroClaw binary matching container architecture
RUN set -eux; \
    case "$(uname -m)" in \
      x86_64)  ARCH="x86_64-unknown-linux-gnu" ;; \
      aarch64) ARCH="aarch64-unknown-linux-gnu" ;; \
      *)       echo "Unsupported arch: $(uname -m)" && exit 1 ;; \
    esac; \
    if [ "${ZEROCLAW_VERSION}" = "latest" ]; then \
      DOWNLOAD_URL="https://github.com/slayer/zeroclaw/releases/latest/download/zeroclaw-${ARCH}.tar.gz"; \
    else \
      DOWNLOAD_URL="https://github.com/slayer/zeroclaw/releases/download/${ZEROCLAW_VERSION}/zeroclaw-${ARCH}.tar.gz"; \
    fi; \
    curl -fsSL "${DOWNLOAD_URL}" -o /tmp/zeroclaw.tar.gz && \
    tar xzf /tmp/zeroclaw.tar.gz -C /usr/local/bin/ && \
    chmod +x /usr/local/bin/zeroclaw && \
    rm /tmp/zeroclaw.tar.gz

COPY run.sh /
RUN chmod +x /run.sh

CMD [ "/run.sh" ]
