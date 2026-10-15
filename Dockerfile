FROM python:3.13-slim AS runtime

# Prevent Python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_ROOT_USER_ACTION=ignore
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Copy requirements and install
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --create-home app

# Copy the rest of the application
COPY --chown=app:app . .
RUN mkdir -p /app/resource/uploads && chown -R app:app /app/resource
USER app

# Expose port
EXPOSE 8000

# Start the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log", "--limit-concurrency", "200", "--timeout-graceful-shutdown", "30"]
