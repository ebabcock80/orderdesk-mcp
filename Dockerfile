# Multi-stage build for OrderDesk MCP Server
FROM python:3.12-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy dependency files, LICENSE, and README
COPY pyproject.toml LICENSE README.md ./

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

# Runtime stage
FROM python:3.12-slim as runtime

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY mcp_server/ ./mcp_server/

# Create data directory and set permissions
RUN mkdir -p /data && chown -R appuser:appuser /data /app

# Switch to non-root user
USER appuser

# Expose port (will be overridden by environment variable)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Set environment variables
ENV PYTHONPATH=/app
ENV PORT=8080

# Entry point
ENTRYPOINT ["sh", "-c", "uvicorn mcp_server.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
