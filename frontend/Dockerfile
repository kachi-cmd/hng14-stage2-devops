# =============================================================================
# Stage 1 — builder
# Install ALL dependencies (including devDependencies) so any build steps
# (transpilation, asset bundling etc.) can run. Only production deps get
# carried to the final image.
# =============================================================================
FROM node:20-alpine AS builder

WORKDIR /build

# Copy package files first — Docker layer caches this install as long as
# package.json and package-lock.json don't change. Saves rebuild time.
COPY package*.json ./

# npm ci is preferred over npm install in CI/CD and Dockerfiles:
# it installs the exact locked versions, fails if package-lock.json
# is out of sync, and is faster than npm install.
RUN npm ci --omit=dev


# =============================================================================
# Stage 2 — runtime
# Alpine is ~50MB vs ~900MB for the full node image. We don't need a compiler,
# npm, or dev tooling at runtime — just the node binary and our app files.
# =============================================================================
FROM node:20-alpine

WORKDIR /app

# Copy only the production node_modules from the builder stage
COPY --from=builder /build/node_modules ./node_modules

# Copy application source explicitly
COPY app.js .
COPY package.json .
COPY views/ ./views/

# Non-root user — Alpine uses addgroup/adduser instead of useradd
RUN addgroup -S -g 1001 appgroup \
    && adduser -S -u 1001 -G appgroup appuser \
    && chown -R appuser:appgroup /app

USER appuser

EXPOSE 3000

# wget is available on alpine-node images and is lighter than installing curl.
# Probes the /health endpoint we added in FIX-08.
HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=3 \
    CMD wget -qO- http://localhost:3000/health || exit 1

# Exec form for proper signal handling
CMD ["node", "app.js"]
