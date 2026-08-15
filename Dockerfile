ARG N8N_VERSION=2.32.7

FROM docker.n8n.io/n8nio/n8n:${N8N_VERSION}

LABEL org.opencontainers.image.title="n8n-local"
LABEL org.opencontainers.image.description="Installation locale n8n"
LABEL org.opencontainers.image.version="${N8N_VERSION}"

USER node