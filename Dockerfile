FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY dzshop ./dzshop
RUN pip install --no-cache-dir .
ENV DZSHOP_DB=/data/dzshop.sqlite3
VOLUME /data
EXPOSE 8000
# Runs offline (rule-based) unless ANTHROPIC_API_KEY is provided.
CMD ["uvicorn", "dzshop.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
