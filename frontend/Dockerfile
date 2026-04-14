FROM node:20-slim AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

ARG VITE_API_URL=https://homebidder-api.fly.dev
ENV VITE_API_URL=$VITE_API_URL

COPY . .
RUN npm run build

FROM node:20-slim

WORKDIR /app

COPY --from=builder /app/.output ./.output

EXPOSE 3000
ENV PORT=3000
CMD ["node", ".output/server/index.mjs"]
