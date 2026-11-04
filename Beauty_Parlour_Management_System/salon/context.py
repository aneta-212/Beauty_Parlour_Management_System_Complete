from .models import SalonSettings,Notification
from .access import manager,employee

def site_context(request):
    return {'salon_info':SalonSettings.current(),'is_manager':manager(request.user),'is_beautician':bool(employee(request.user)),
        'unread_count':Notification.objects.filter(user=request.user,read=False).count() if request.user.is_authenticated else 0}
