# =============================================================================
# NovoProtein AI — Multi-Stage Docker Build
# =============================================================================
# Stage 1: Build frontend (Node.js)
# Stage 2: Python runtime with built frontend
# =============================================================================

# ─── Stage 1: Build Frontend ─────────────────────────────────────────────────
FROM node:20-alpine AS frontend-build

WORKDIR /app

# Install dependencies first (cached layer)
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts

# Copy source and build
COPY tsconfig.json vite.config.ts tailwind.config.js postcss.config.js index.html ./
COPY src/ ./src/
RUN npm run build


# ─── Stage 2: Python Runtime ─────────────────────────────────────────────────
FROM python:3.13-slim AS runtime

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (cached layer)
COPY server/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy server source
COPY server/ ./server/

# Copy built frontend from Stage 1
COPY --from=frontend-build /app/dist ./dist/

# Create directories for persistent data
RUN mkdir -p server/uploads/pdb server/data

# Expose port
EXPOSE 8787

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8787/api/health || exit 1

# Run with uvicorn
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8787"]
