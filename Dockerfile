FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy source
COPY pebbles/ ./pebbles/

# Run in loop mode by default
CMD ["pebbles", "run", "--loop"]