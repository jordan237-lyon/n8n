FROM node:24.15.0-bookworm-slim AS dependencies

WORKDIR /app

COPY package.json package-lock.json ./

RUN npm ci --omit=dev --ignore-scripts \
    && npm cache clean --force


FROM node:24.15.0-bookworm-slim AS runtime

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        fontconfig \
        fonts-liberation2 \
        libreoffice-writer \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/*

ENV NODE_ENV=production

WORKDIR /app

COPY --from=dependencies --chown=node:node /app/node_modules ./node_modules
COPY --chown=node:node package.json server.js ./
COPY fonts/ /usr/local/share/fonts/custom/

RUN fc-cache -f

USER node

EXPOSE 3000

HEALTHCHECK \
    --interval=30s \
    --timeout=5s \
    --start-period=5s \
    --retries=3 \
    CMD node -e "fetch('http://127.0.0.1:3000/health').then(r => { if (!r.ok) process.exit(1) }).catch(() => process.exit(1))"

CMD ["node", "server.js"]
