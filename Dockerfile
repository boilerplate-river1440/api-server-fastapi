FROM python:3.13-slim

# 1. Install uv by copying the binaries from the official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 2. Set the working directory
WORKDIR /app

# 3. Copy only dependency files first (optimizes Docker layer caching)
COPY pyproject.toml uv.lock ./

# 4. Install dependencies without the application code itself
RUN uv sync --frozen --no-cache --no-install-project

# 5. Copy the rest of your application code (including your app/ folder)
COPY . .

# 6. Run a final sync to include your local package (if applicable)
RUN uv sync --frozen --no-cache

# 7. Run the FastAPI application using Python 3.13's virtual environment binary
# Note: "fastapi run" expects a path relative to WORKDIR, so "app/main.py" is exactly right here.
CMD ["/app/.venv/bin/fastapi", "run", "app/main.py", "--port", "8000", "--host", "0.0.0.0"]