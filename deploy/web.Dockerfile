FROM node:22-bookworm-slim AS build
WORKDIR /build
COPY vue/package.json vue/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY vue/ ./
ENV VITE_BASE_URL=/api
RUN npm run build

FROM nginx:1.28-alpine
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /build/dist /usr/share/nginx/html
