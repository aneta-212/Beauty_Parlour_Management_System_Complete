from django.core.management.base import BaseCommand
from salon.models import Staff, Service
class Command(BaseCommand):
    help='Add two clearly labelled demo beauticians, without changing existing staff.'
    def handle(self,*args,**kwargs):
        for name in ['Demo Beautician 1','Demo Beautician 2']:
            person,created=Staff.objects.get_or_create(name=name)
            if created: person.services.set(Service.objects.all())
        self.stdout.write(self.style.SUCCESS('Demo staff ready. Edit names, services and working hours in Staff & leave.'))
