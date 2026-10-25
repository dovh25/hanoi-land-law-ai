FROM python:3.12.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /usr/local/bin/uv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY backend ./backend
COPY benchmarks ./benchmarks
COPY preprocess ./preprocess
COPY law_crawler ./law_crawler
COPY batch ./batch
RUN uv sync --frozen --no-dev
RUN useradd --uid 10001 --create-home app && mkdir -p /app/data && chown -R app:app /app
ENV PATH="/app/.venv/bin:$PATH"
USER app
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
