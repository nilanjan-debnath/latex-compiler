# syntax=docker/dockerfile:1
# Set versions as arguments
ARG PYTHON_VERSION=3.12
ARG UV_VERSION=0.8.3

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv_builder

###########################
# ---- Builder Stage ---- #
###########################
# Use slim (Debian/glibc) for compatibility with texlive (Ubuntu-based)
FROM python:${PYTHON_VERSION}-slim AS builder

WORKDIR /project

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Install uv from the builder stage
COPY --from=uv_builder /uv /uvx /bin/

# Copy dependency files for layer caching
COPY pyproject.toml uv.lock ./

# Create venv and install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-install-project --no-default-groups

# Copy source code
COPY . .

# Install the project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-default-groups

#########################
# ---- Final Stage ---- #
#########################
FROM python:${PYTHON_VERSION}-slim AS runtime

WORKDIR /project

ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Install texlive and runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    # Add texlive packages you need:
    texlive-latex-base \
    texlive-latex-extra \
    texlive-latex-recommended \
    texlive-fonts-recommended \
    texlive-fonts-extra \
    texlive-xetex \
    texlive-luatex \
    texlive-science \
    latexmk \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN groupadd -r appgroup && useradd -r -g appgroup appuser

# Copy application files including virtual environment from the builder stage.
COPY --from=builder /project .

# Give appuser full ownership of the directory
RUN chown -R appuser:appgroup /project

# Add venv to PATH
ENV PATH="/project/.venv/bin:$PATH"

# Make entrypoint executable
RUN chmod +x ./entrypoint.sh

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Set entrypoint
ENTRYPOINT ["./entrypoint.sh"]

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/healthz || exit 1
