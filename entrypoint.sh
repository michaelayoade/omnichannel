#!/bin/sh

# Exit immediately if a command exits with a non-zero status
set -e

# Wait for the database to be ready
echo "Waiting for database..."
python -c "
import sys
import time
import psycopg2
import os
from urllib.parse import urlparse

# Extract database connection info from DATABASE_URL
url = urlparse(os.environ.get('DATABASE_URL', ''))
dbname = url.path[1:]
user = url.username
password = url.password
host = url.hostname
port = url.port

# Wait for database to be available
retries = 0
max_retries = 30
while retries < max_retries:
    try:
        conn = psycopg2.connect(
            dbname=dbname,
            user=user,
            password=password,
            host=host,
            port=port)
        conn.close()
        break
    except psycopg2.OperationalError:
        retries += 1
        sys.stderr.write('Waiting for database... {}/{}\n'.format(retries, max_retries))
        time.sleep(2)

if retries >= max_retries:
    sys.stderr.write('Database not available after {} retries\n'.format(max_retries))
    sys.exit(1)
"
echo "Database is ready!"

# Apply database migrations
echo "Applying migrations..."
python manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Execute the command passed to entrypoint
exec "$@"
