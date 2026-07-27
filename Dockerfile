# python:3.14-slim, not alpine: alpine's musl libc means several Python
# packages (psycopg included) build from source instead of installing a
# wheel, turning a fast build into a slow one to save a little image size.
# The version matches the host's development interpreter (see
# requirements.txt's notes on Python 3.14 wheel availability) so that a
# difference in behaviour between `uvicorn app.main:app --reload` on the
# host and `docker compose up` can never be a Python-version discrepancy
# hiding underneath it.
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/code

WORKDIR /code

# requirements.txt is copied and installed before the rest of the
# source. Docker caches each layer, so editing a template or a route
# afterwards does not reinstall FastAPI and everything beneath it.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# "sh", not "./scripts/entrypoint.sh": the latter requires the file's
# executable bit, which a checkout on Windows does not preserve, and
# the resulting "permission denied" is easy to misread as a Docker
# problem rather than a file-mode one. Invoking sh explicitly sidesteps
# the issue entirely.
CMD ["sh", "/code/scripts/entrypoint.sh"]
