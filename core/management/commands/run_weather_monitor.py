"""
Django management command: run_weather_monitor
================================================
Usage:
    python manage.py run_weather_monitor         # runs once
    python manage.py run_weather_monitor --loop  # runs every 5 min forever

Place this file at:
    core/management/commands/run_weather_monitor.py

Create the __init__.py files too:
    core/management/__init__.py
    core/management/commands/__init__.py
"""

from django.core.management.base import BaseCommand
from core.weather_monitor import run_monitor_once, run_monitor_loop


class Command(BaseCommand):
    help = "Run the GigSure weather monitor to auto-create claims"

    def add_arguments(self, parser):
        parser.add_argument(
            '--loop',
            action='store_true',
            help='Run continuously every 5 minutes instead of once',
        )

    def handle(self, *args, **options):
        if options['loop']:
            self.stdout.write(self.style.SUCCESS("🔁 Starting monitor in loop mode..."))
            run_monitor_loop()
        else:
            self.stdout.write(self.style.SUCCESS("🌦️  Running weather monitor (single pass)..."))
            run_monitor_once()
            self.stdout.write(self.style.SUCCESS("✅ Done."))