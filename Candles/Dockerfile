
# ===============================
# Stage 1 - Build Tailwind CSS
# ===============================
FROM node:22-alpine AS frontend

WORKDIR /frontend

COPY package*.json ./
RUN npm install

COPY . .

RUN npx @tailwindcss/cli \
    -i ./static/input.css \
    -o ./static/output.css \
    --minify

# ===============================
# Stage 2 - Flask + Node.js
# ===============================
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install Node.js 22 and npm for Debian
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    ca-certificates curl gnupg \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
    | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" \
    > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && node --version \
    && npm --version \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY --from=frontend /frontend/ .

EXPOSE 3000

CMD ["flask", "--app", "app", "run", "--host=0.0.0.0", "--port=3000"]
