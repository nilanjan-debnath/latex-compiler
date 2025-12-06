# Set versions as arguments
ARG PYTHON_VERSION=3.12
ARG UV_VERSION=0.8.3

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv_builder

###########################
# ---- Builder Stage ---- #
###########################
# This stage installs dependencies into a virtual environment.
FROM python:${PYTHON_VERSION}-alpine AS builder

WORKDIR /project

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Install the uv tool for Python package management.
COPY --from=uv_builder /uv /uvx /bin/

# Install build dependencies required to compile packages like psutil.
RUN apk add --no-cache \
    gcc \
    python3-dev \
    musl-dev \
    linux-headers \
    make

# Copy dependency definition files to leverage Docker layer caching.
COPY pyproject.toml uv.lock ./

# Create a virtual environment and install dependencies in one step.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-install-project --no-default-groups

# Install OpenTelemetry dependencies using opentelemetry-bootstrap to ensure compatibility
RUN --mount=type=cache,target=/root/.cache/uv \
    uv add --group otel-deploy $(uv run opentelemetry-bootstrap -a requirements)

# Backup the modified toml and lock files
RUN cp pyproject.toml pyproject.toml.bak && cp uv.lock uv.lock.bak

# Copy the rest of the application source code.
COPY . .

# Restore the backup (Overwriting the host files with the container's modified versions)
RUN mv pyproject.toml.bak pyproject.toml && mv uv.lock.bak uv.lock

# Install the project itself using the frozen lock file to ensure reproducible builds
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-default-groups --group otel-deploy

#########################
# ---- Final Stage ---- #
#########################
# This stage creates the lean, secure final image.
FROM python:${PYTHON_VERSION}-alpine AS runtime

WORKDIR /project

# Set environment variable for unbuffered output.
ENV PYTHONUNBUFFERED=1

# Install only the runtime OS dependencies needed.
RUN apk add --no-cache \
    tectonic \
    curl

# Create a non-root user and group for security.
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

# Copy application files including virtual environment from the builder stage.
COPY --from=builder --chown=appuser:appgroup /project .

# Add the virtual environment's bin directory to the PATH.
ENV PATH="/project/.venv/bin:$PATH"

# Make the entrypoint script executable.
RUN chmod +x ./entrypoint.sh

# Switch to the non-root user.
USER appuser

# Expose the application port.
EXPOSE 8000

# Set the container's entrypoint.
ENTRYPOINT ["./entrypoint.sh"]

# Add a health check to monitor the application's status.
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/healthz || exit 1
