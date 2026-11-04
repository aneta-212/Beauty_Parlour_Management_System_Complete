from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from .models import Staff

def manager(user):
    return user.is_authenticated and (user.is_superuser or (user.is_staff and not Staff.objects.filter(user=user).exists()))

def employee(user):
    return Staff.objects.filter(user=user,active=True).first() if user.is_authenticated else None

def manager_only(view):
    @login_required
    @wraps(view)
    def wrapped(request,*args,**kwargs):
        if not manager(request.user): raise PermissionDenied
        return view(request,*args,**kwargs)
    return wrapped
