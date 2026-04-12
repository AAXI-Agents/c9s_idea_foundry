FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY src/ src/
COPY knowledge/ knowledge/
RUN pip install --no-cache-dir .

# Create non-root user
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --ingroup appgroup --home /app appuser && \
    chown -R appuser:appgroup /app

ENV HOME=/app
USER appuser

ENV SERVER_ENV=UAT
EXPOSE 8000

CMD ["python", "-m", "uvicorn", "crewai_productfeature_planner.apis:app", "--host", "0.0.0.0", "--port", "8000"]
