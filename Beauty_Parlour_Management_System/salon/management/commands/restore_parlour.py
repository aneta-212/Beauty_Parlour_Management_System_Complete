from django.core.management.base import BaseCommand,CommandError
from salon.backup import restore_backup
class Command(BaseCommand):
    help='Restore a trusted project backup while the server is stopped; first makes a recovery backup.'
    def add_arguments(self,parser):
        parser.add_argument('archive')
        parser.add_argument('--confirm-restore',action='store_true')
    def handle(self,*args,**options):
        if not options['confirm_restore']:raise CommandError('Stop the server, then pass --confirm-restore to replace the current database and media.')
        try:path=restore_backup(options['archive'])
        except Exception as exc:raise CommandError(str(exc))
        self.stdout.write(self.style.SUCCESS(f'Restored. Recovery copy: {path}. Run manage.py migrate before restarting.'))
