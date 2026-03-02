# Stage 1: Build Microsandbox (Rust)
FROM rust:1.75-slim-bookworm as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    git \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Clone specific version of microsandbox with volume support
WORKDIR /usr/src
RUN git clone https://github.com/TJKlein/microsandbox.git
WORKDIR /usr/src/microsandbox
# Build release binary
RUN cargo build --release

# Stage 2: Runtime (Python)
FROM python:3.10-slim-bookworm

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Setup Microsandbox
COPY --from=builder /usr/src/microsandbox/target/release/msbserver /usr/local/bin/msbserver
ENV MICROSANDBOX_PATH=/usr/local/bin/msbserver

# Setup AgentKernel
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e .

# Configure environment
ENV SANDBOX_TYPE=microsandbox
ENV PYTHONPATH=/app

# Default command
CMD ["/bin/bash"]
