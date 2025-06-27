"""
Management command to wait for database to be available.
"""

import time

from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError

from omnichannel_core.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class Command(BaseCommand):
    """Django command to pause execution until database is available"""

    help = "Waits for database connection to be available"

    def handle(self, *args, **options):
        """Handle the command"""
        self.stdout.write("Waiting for database...")
        db_conn = None
        max_tries = 30
        tries = 0

        logger.info("Starting database connection check")

        while not db_conn and tries < max_tries:
            try:
                # Get the default database connection
                db_conn = connections["default"]
                # Test the connection
                db_conn.cursor()
                self.stdout.write(self.style.SUCCESS("Database available!"))
                logger.info("Database connection successful")
            except OperationalError:
                tries += 1
                logger.warning(
                    f"Database unavailable, waiting 1 second... (try {tries}/{max_tries})"
                )
                time.sleep(1)

        if tries >= max_tries:
            logger.error(
                "Maximum connection attempts reached. Could not connect to database."
            )
            raise OperationalError(
                "Could not connect to database after multiple attempts"
            )
