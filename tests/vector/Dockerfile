FROM python:3.11-slim@sha256:9534e5a8e315485d4061ed659af0fd78a284c015f9b73661b41d6bab25604534
COPY requirements.lock /tmp/vector-requirements.txt
RUN pip install --no-cache-dir -r /tmp/vector-requirements.txt && pip check
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/workspace HOME=/tmp ANONYMIZED_TELEMETRY=False
WORKDIR /workspace
USER 65534:65534
