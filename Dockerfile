FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml .
COPY server/ server/
RUN pip install --no-cache-dir -e .

EXPOSE 8000
CMD ["uvicorn", "server.http_facade:app", "--host", "0.0.0.0", "--port", "8000"]
