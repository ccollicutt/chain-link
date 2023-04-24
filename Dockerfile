# Dockerfile
FROM python:3.11-slim
COPY requirements.txt /
RUN set -ex && \
    pip install -r requirements.txt
COPY app.py gunicorn-run.sh /app/
RUN useradd gunicorn -u 10001 --user-group
USER 10001
WORKDIR /app

ENTRYPOINT [ "/app/gunicorn-run.sh" ]