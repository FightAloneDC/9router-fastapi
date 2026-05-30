# ── Dev ── (vite dev server with hot-reload)
FROM node:22-alpine AS dev

ARG UID=1000
ARG GID=1000

RUN apk add --no-cache shadow && \
    groupmod -g ${GID} node 2>/dev/null || true && \
    usermod -u ${UID} -g ${GID} node 2>/dev/null || true && \
    mkdir -p /app && chown node:node /app

WORKDIR /app

COPY --chown=node:node package.json package-lock.json ./

USER node

# Install deps as node so node_modules is owned by node
RUN npm ci

# Source is mounted as volume — no COPY needed
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]

# ── Build ──
FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# ── Production ── (nginx serving built assets)
FROM nginx:alpine AS prod

# Copy built assets
COPY --from=build /app/dist /usr/share/nginx/html

# Nginx config: SPA routing + API proxy
RUN cat > /etc/nginx/conf.d/default.conf <<'EOF'
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # Proxy API requests to backend
    location /api/ {
        proxy_pass http://backend:9000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support (for console log)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }
}
EOF

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
