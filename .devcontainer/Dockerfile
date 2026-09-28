FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

WORKDIR /workspace

COPY requirements.txt requirements-dev.txt ./
RUN python -m pip install --no-cache-dir -r requirements-dev.txt
