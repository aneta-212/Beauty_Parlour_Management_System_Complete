from datetime import datetime, time, timedelta
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from django.db.models import F
from django.utils import timezone
from .models import Staff, StaffLeave, Appointment, Reservation, SalonSettings, ScheduleBlock, AppointmentItem, WaitlistEntry
from .events import audit, notify
from .selection import selection

ACTIVE = ['Pending', 'Approved']


def can_book(staff, service, day, slot, exclude=None, user=None, duration=None, services=None):
    duration = duration or service.duration
    required = services or [service]
    if any(not staff.services.filter(pk=x.pk).exists() for x in required): return False
    config = SalonSettings.current()
    if day > timezone.localdate() + timedelta(days=config.booking_horizon_days): return False
    if duration < 1 or not staff.active or not staff.services.filter(pk=service.pk).exists():
        return False
    if str(day.weekday()) not in staff.weekdays.split(',') or StaffLeave.objects.filter(staff=staff, date=day).exists():
        return False
    opening, closing = (config.sunday_open, config.sunday_close) if day.weekday() == 6 else (config.weekday_open, config.weekday_close)
    # Unsaved default TimeFields can be strings.
    opening = time.fromisoformat(opening) if isinstance(opening,str) else opening
    closing = time.fromisoformat(closing) if isinstance(closing,str) else closing
    start = timezone.make_aware(datetime.combine(day, slot))
    end = start + timedelta(minutes=duration)
    if start <= timezone.now() or slot.second or slot.microsecond or slot.minute % 15:
        return False
    if slot < max(opening, staff.start_time) or end.date() != day or end.time() > min(closing, staff.end_time):
        return False
    from django.db.models import Q
    if ScheduleBlock.objects.filter(Q(staff=staff)|Q(staff__isnull=True),date=day,start_time__lt=end.time(),end_time__gt=slot).exists(): return False
    minute = slot.hour * 60 + slot.minute
    if Reservation.objects.filter(staff=staff, date=day, minute__gte=minute, minute__lt=minute+duration).exclude(appointment_id=exclude).exists():
        return False
    # Also account for legacy appointments that do not have reservation rows.
    existing = Appointment.objects.filter(date=day, status__in=ACTIVE).exclude(pk=exclude).select_related('service')
    for a in existing:
        if a.staff_id == staff.pk or (user and a.user_id == user.pk):
            a_start = a.time.hour * 60 + a.time.minute
            a_end = a_start + (a.duration_minutes or a.service.duration)
            if minute < a_end and minute + duration > a_start:
                return False
    return True


def slots(staff, service, day, exclude=None, user=None, duration=None, services=None):
    return [f'{h:02d}:{m:02d}' for h in range(0,24) for m in (0,15,30,45)
            if can_book(staff, service, day, time(h,m), exclude, user, duration, services)]


def lock_schedule():
    # First statement acquires SQLite's write lock; row locks cover other DBs.
    Staff.objects.update(name=F('name'))
    list(Staff.objects.select_for_update().values_list('pk', flat=True))


@transaction.atomic
def save_booking(form, user, appointment_id=None, actor=None, walk_in=False):
    lock_schedule()
    a = form.save(commit=False)
    a.staff = Staff.objects.get(pk=a.staff_id)
    actor = actor or user
    if appointment_id:
        previous = Appointment.objects.get(pk=appointment_id, **({'user':user} if not walk_in else {}))
        start = timezone.make_aware(datetime.combine(previous.date, previous.time))
        if previous.status not in ACTIVE or start <= timezone.now() + timedelta(hours=0 if walk_in else SalonSettings.current().change_notice_hours):
            raise ValidationError('This appointment can no longer be changed under the cancellation/rescheduling notice policy.')
        duration, price = previous.duration_minutes or previous.service.duration, previous.quoted_price
        required = [item.service for item in previous.items.select_related('service')] or [previous.service]
        a.service = previous.service
        a.package = previous.package
    else:
        required,duration,price,package = selection(a.service_id,[x.pk for x in form.cleaned_data.get('extras',[])],form.cleaned_data['package'].pk if form.cleaned_data.get('package') else None,a.date)
        a.service,a.package = required[0],package
    if not can_book(a.staff, a.service, a.date, a.time, appointment_id, user, duration, required):
        raise ValidationError('That time is no longer available. Please choose another slot.')
    a.user, a.status, a.duration_minutes = user, 'Approved' if walk_in else 'Pending', duration
    a.walk_in = walk_in or a.walk_in
    a.reminder_sent_at = None
    a.quoted_price = price if price is not None else a.service.price
    a.save()
    if not appointment_id:
        AppointmentItem.objects.bulk_create([AppointmentItem(appointment=a,service=x,name=x.name,price=x.price,duration=x.duration) for x in required])
    a.reservations.all().delete()
    minute = a.time.hour*60 + a.time.minute
    Reservation.objects.bulk_create([Reservation(appointment=a, staff=a.staff, date=a.date, minute=m) for m in range(minute, minute+duration)])
    audit(actor,'Booking rescheduled' if appointment_id else 'Booking created',f'Appointment #{a.pk}: {a.status}')
    notify(user,f'Appointment #{a.pk} is {a.status.lower()} for {a.date} at {a.time}.')
    if user:
        WaitlistEntry.objects.filter(user=user,service__in=required,date=a.date,status__in=['Waiting','Offered']).update(status='Booked')
    return a


@transaction.atomic
def change_status(pk, status, user, customer=False):
    lock_schedule()
    a = Appointment.objects.select_related('service').get(pk=pk)
    if customer and a.user_id != user.pk:
        raise ValidationError('This appointment does not belong to you.')
    if a.status not in ACTIVE:
        raise ValidationError('This appointment has already been closed.')
    start = timezone.make_aware(datetime.combine(a.date, a.time))
    if customer and (status != 'Cancelled' or start <= timezone.now() + timedelta(hours=SalonSettings.current().change_notice_hours)):
        raise ValidationError('Only upcoming appointments can be cancelled.')
    if status == 'Approved':
        if not a.staff or not can_book(a.staff,a.service,a.date,a.time,a.pk,a.user,a.duration_minutes or None,[i.service for i in a.items.select_related('service')] or [a.service]):
            raise ValidationError('Assign an available staff member and time before approving.')
    elif status == 'Completed':
        if a.status != 'Approved' or start + timedelta(minutes=a.duration_minutes or a.service.duration) > timezone.now():
            raise ValidationError('Complete an approved appointment only after its scheduled end.')
    elif status == 'No-show':
        if a.status != 'Approved' or start > timezone.now():
            raise ValidationError('Mark no-show only after an approved appointment has started.')
    elif status not in ['Rejected','Cancelled']:
        raise ValidationError('Invalid status change.')
    a.status = status
    a.save(update_fields=['status'])
    if status not in ACTIVE:
        a.reservations.all().delete()
    audit(user,'Appointment status changed',f'Appointment #{a.pk}: {status}')
    notify(a.user,f'Appointment #{a.pk} is now {status.lower()}.')
    return a
