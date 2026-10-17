#!/usr/bin/env bash
set -euo pipefail
mkdir -p "${FARMCART_DATA_DIR:-.}"
# A marker prevents deleted samples from being recreated on every deployment.
if [ ! -f "${FARMCART_DATA_DIR:-.}/db.sqlite3" ]; then
    seed_first_run=1
else
    seed_first_run=0
fi
python manage.py migrate --noinput
if [ "$seed_first_run" = 1 ]; then
    python manage.py seed_demo
fi
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers 1 --threads 2 --timeout 120 --access-logfile -
