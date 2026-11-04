from .models import AuditEvent,Notification

def audit(actor,action,detail):
    AuditEvent.objects.create(actor=actor if getattr(actor,'is_authenticated',False) else None,action=action,detail=str(detail)[:500])

def notify(user,text,link='/accounts/profile/'):
    if user:
        Notification.objects.create(user=user,text=text[:500],link=link)
