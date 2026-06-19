FROM node:20-alpine AS build

WORKDIR /app
COPY widget/package.json ./
RUN npm install --frozen-lockfile 2>/dev/null || npm install

COPY widget/ ./
ARG VITE_API_BASE=http://localhost:8000
ENV VITE_API_BASE=${VITE_API_BASE}
RUN npm run build

# ── Serve with nginx ───────────────────────────────────────────────────────
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html/widget
COPY docker/widget-nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
