from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from salon.models import Notification
from salon.scheduling import lock_schedule
class Command(BaseCommand):
    help='Deliver pending notification emails. Run one worker; configure SMTP for real email.'
    def handle(self,*args,**options):
        sent=0
        ids=list(Notification.objects.filter(email_requested=True,email_sent_at__isnull=True).values_list('pk',flat=True)[:200])
        for pk in ids:
            with transaction.atomic():
                lock_schedule()
                item=Notification.objects.select_related('user').get(pk=pk)
                if item.email_sent_at or not item.user.email:continue
                try:send_mail('Beauty Parlour update',item.text+'\n\n'+settings.SITE_URL.rstrip('/')+item.link,settings.DEFAULT_FROM_EMAIL,[item.user.email],fail_silently=False)
                except Exception as exc:
                    self.stderr.write(f'Notification #{pk} was not sent ({type(exc).__name__}); retry later.');continue
                item.email_sent_at=timezone.now();item.save(update_fields=['email_sent_at']);sent+=1
        self.stdout.write(f'Processed {sent} emails using {settings.EMAIL_BACKEND}.')
