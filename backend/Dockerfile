FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt

COPY . .

# invoked through sh rather than executed directly: /app is replaced by a bind
# mount at runtime, so the exec bit set in the image would not survive
ENTRYPOINT ["sh", "/app/entrypoint.sh"]
# Shell form so ${PORT} is expanded at run time. Railway assigns a port and
# requires the process to listen on it; 8000 is the local default.
# --reload is a development flag, switched on only by docker-compose.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} ${UVICORN_RELOAD:+--reload}"]
