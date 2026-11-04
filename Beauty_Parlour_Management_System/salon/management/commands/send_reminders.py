from datetime import datetime,timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from salon.models import Appointment
from salon.events import notify
from salon.scheduling import lock_schedule
class Command(BaseCommand):
    help='Queue reminders for approved account bookings in the next 24 hours. Run hourly.'
    def handle(self,*args,**options):
        now=timezone.now();count=0
        with transaction.atomic():
            lock_schedule()
            for a in Appointment.objects.filter(status='Approved',user__isnull=False,reminder_sent_at__isnull=True,date__gte=timezone.localdate(),date__lte=timezone.localdate()+timedelta(days=1)):
                start=timezone.make_aware(datetime.combine(a.date,a.time))
                if now<start<=now+timedelta(hours=24):
                    notify(a.user,f'Reminder: appointment #{a.pk} on {a.date} at {a.time}.')
                    a.reminder_sent_at=now;a.save(update_fields=['reminder_sent_at']);count+=1
        self.stdout.write(f'Queued {count} reminders.')
