from decimal import Decimal
from django.core.exceptions import ValidationError
from .models import Service,Package

def selection(service_id,extra_ids=(),package_id=None,day=None):
    package=None
    try:
        if package_id:
            package=Package.objects.get(pk=package_id,active=True)
            if package.valid_until and day and day>package.valid_until:
                raise ValidationError('This package has expired for the selected date.')
            services=list(package.services.order_by('pk'))
        else:
            ids=list(dict.fromkeys([int(service_id)]+[int(x) for x in extra_ids if x]))
            services=list(Service.objects.filter(pk__in=ids).order_by('pk'))
            if len(services)!=len(ids): raise ValidationError('Select valid services.')
            services.sort(key=lambda x:ids.index(x.pk))
    except (ValueError,TypeError,Package.DoesNotExist):
        raise ValidationError('Choose a service or an active package.')
    if not services: raise ValidationError('This package has no services.')
    duration=sum(x.duration for x in services)
    price=sum((x.price for x in services),Decimal('0.00'))-(package.discount if package else 0)
    if any(x.duration<1 or x.price<0 for x in services) or duration>1440 or price<0 or price>Decimal('999999.99'):
        raise ValidationError('The selected services or package need a manager to correct their price or duration.')
    return services,duration,price,package
