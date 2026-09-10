FROM python:3.11-slim@sha256:9534e5a8e315485d4061ed659af0fd78a284c015f9b73661b41d6bab25604534
COPY requirements.txt /tmp/test-requirements.txt
RUN pip install --no-cache-dir -r /tmp/test-requirements.txt
ENV PYTHONDONTWRITEBYTECODE=1
WORKDIR /workspace
USER 65534:65534
