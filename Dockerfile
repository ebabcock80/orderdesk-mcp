# Multi-stage build for OrderDesk MCP Server
FROM python:3.12-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml LICENSE README.md ./

# Install Python dependencies (including optional webui for full functionality)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .[webui]

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
RUN mkdir -p /app/data && chown -R appuser:appuser /app

# NOTE: Running as root for development/testing to avoid volume permission issues
# For production, uncomment the USER directive below:
# USER appuser

# Expose port
EXPOSE 8080

# Volume for persistent data (SQLite database)
VOLUME ["/app/data"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8080}/health || python -c "import sys; sys.exit(0)"

# Set environment variables
ENV PYTHONPATH=/app
ENV PORT=8080
ENV DATABASE_URL=sqlite:///app/data/app.db

# Default command: stdio MCP server
# Override with: docker run ... uvicorn mcp_server.main:app --host 0.0.0.0 --port 8080
CMD ["python", "-m", "mcp_server.main"]
