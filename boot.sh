#!/bin/sh
exec gunicorn -c gunicorn_config.py app:app
