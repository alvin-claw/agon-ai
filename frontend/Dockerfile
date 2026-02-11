FROM node:24-slim

WORKDIR /app

RUN npm install -g bun

COPY package.json bun.lock* ./
RUN bun install --frozen-lockfile

COPY . .

EXPOSE 3000
CMD ["bun", "dev"]
