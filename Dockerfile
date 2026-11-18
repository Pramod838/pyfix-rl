FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source — hidden/ is excluded by .dockerignore and bind-mounted at runtime
COPY . .
RUN pip install --no-cache-dir -e .

# Create a non-root worker user for the worker service
RUN groupadd -r worker && \
    useradd -r -g worker -s /bin/false -m -d /home/worker worker

# OCI labels
LABEL org.opencontainers.image.title="pyfix-rl" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.description="Python Code-Repair RL Environment"

# Default user is worker (non-root). Override for grader if needed.
USER worker
