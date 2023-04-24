#!/bin/bash

: ${PORT:=8000}
gunicorn --chdir /app -w 1 --threads 2 -b 0.0.0.0:${PORT} app:app
