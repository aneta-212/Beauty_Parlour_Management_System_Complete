from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from salon.backup import create_backup
class Command(BaseCommand):
    help='Create a consistent SQLite and media backup.'
    def handle(self,*args,**options):
        folder=Path(settings.BASE_DIR)/'backups';folder.mkdir(exist_ok=True)
        path=create_backup(folder/('parlour_'+timezone.now().strftime('%Y%m%d_%H%M%S_%f')+'.zip'))
        self.stdout.write(self.style.SUCCESS(str(path)))
