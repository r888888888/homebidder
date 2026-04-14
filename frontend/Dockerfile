FROM node:22-slim AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

ARG VITE_API_URL=https://homebidder-api.fly.dev
ENV VITE_API_URL=$VITE_API_URL

COPY . .
RUN npm run build

FROM node:22-slim

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --omit=dev

COPY --from=builder /app/dist ./dist
COPY serve.mjs ./

EXPOSE 3000
ENV PORT=3000
CMD ["node", "serve.mjs"]
