from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from .models import Service, Appointment
from .forms import AppointmentForm, ContactForm


def home(request):
    return render(request, 'home.html')

def services(request):
    return render(request, 'services.html', {'services': Service.objects.order_by('name')})

def about(request):
    return render(request, 'about.html')

def gallery(request):
    return render(request, 'gallery.html')

def contact(request):
    form = ContactForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Your message has been saved for our team.')
        return redirect('contact')
    return render(request, 'contact.html', {'form': form})

from functools import wraps
from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4
from django.urls import reverse
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.db import transaction, IntegrityError
from django.db.models import Sum, F
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import Staff, StaffLeave, Invoice, Payment, ContactMessage
from .forms import StaffForm, LeaveForm, ServiceForm, InvoiceForm, PaymentForm
from .scheduling import save_booking, change_status, slots, lock_schedule, ACTIVE
from django.core.exceptions import ValidationError


from .access import manager_only as staff_only, manager, employee
from .events import audit, notify


@login_required
def booking(request, pk=None):
    a = get_object_or_404(Appointment,user=request.user,pk=pk) if pk else None
    if a and (a.status not in ACTIVE or timezone.make_aware(datetime.combine(a.date,a.time)) <= timezone.now()):
        messages.error(request,'This appointment can no longer be changed.')
        return redirect('profile')
    user_profile=getattr(request.user,'userprofile',None)
    initial={'date':request.GET.get('date',''),'package':request.GET.get('package',''),'name':request.user.get_full_name() or request.user.username,'email':request.user.email,'phone':user_profile.phone if user_profile else '', 'service':request.GET.get('service')}
    form=AppointmentForm(request.POST if request.method=='POST' else None, instance=a, initial=None if a else initial, user=request.user)
    if request.method=='POST' and form.is_valid():
        try:
            save_booking(form,request.user,pk)
        except (ValidationError,IntegrityError) as exc:
            form.add_error(None,exc if isinstance(exc,ValidationError) else 'This slot has just been taken. Choose another time.')
        else:
            messages.success(request,'Appointment requested. Staff will review it shortly.')
            return redirect('profile')
    return render(request,'booking.html',{'form':form,'rescheduling':bool(a),'appointment':a})


@login_required
def available_slots(request):
    from .selection import selection
    from .models import AppointmentItem
    try:
        day=date.fromisoformat(request.GET.get('date',''))
        a=None
        if request.GET.get('appointment'):
            a=get_object_or_404(Appointment,pk=request.GET['appointment'],**({} if manager(request.user) and request.GET.get('walk_in')=='1' else {'user':request.user}))
            required=[i.service for i in a.items.select_related('service')] or [a.service]
            duration=a.duration_minutes or a.service.duration
            price=a.quoted_price
        else:
            required,duration,price,_=selection(request.GET.get('service'),request.GET.getlist('extras'),request.GET.get('package'),day)
        people=Staff.objects.filter(active=True)
        for treatment in required:people=people.filter(services=treatment)
        data={'staff':[{'id':x.pk,'name':x.name} for x in people], 'slots':[], 'duration':duration,'price':str(price)}
        person=people.filter(pk=request.GET.get('staff') or None).first()
        customer=request.user
        if request.GET.get('walk_in')=='1' and manager(request.user):
            from django.contrib.auth.models import User
            customer=User.objects.filter(pk=request.GET.get('customer')).first() if request.GET.get('customer') else None
        if person:data['slots']=slots(person,required[0],day,a.pk if a else None,customer,duration,required)
        return JsonResponse(data)
    except (ValueError,TypeError,ValidationError):
        return JsonResponse({'staff':[],'slots':[],'error':'Select valid services and a date within the offer period.'})


@login_required
@require_POST
def cancel_booking(request,pk):
    get_object_or_404(Appointment,pk=pk,user=request.user)
    try: change_status(pk,'Cancelled',request.user,customer=True)
    except ValidationError as exc: messages.error(request,' '.join(exc.messages))
    else: messages.success(request,'Appointment cancelled.')
    return redirect('profile')


@login_required
def dashboard(request):
    if not manager(request.user):
        person=employee(request.user)
        if not person:raise PermissionDenied
        return render(request,'beautician_dashboard.html',{'person':person,'appointments':Appointment.objects.filter(staff=person,date__gte=timezone.localdate()).select_related('service').order_by('date','time')[:100]})
    appointments=Appointment.objects.select_related('service','staff','invoice').order_by('-date','-time')
    selected=request.GET.get('status','')
    if selected in dict(Appointment.STATUS): appointments=appointments.filter(status=selected)
    invoices=Invoice.objects.prefetch_related('payments')
    return render(request,'dashboard.html',{
        'appointments':appointments[:100], 'selected':selected,'statuses':Appointment.STATUS,
        'total_appointments':Appointment.objects.count(),'pending':Appointment.objects.filter(status='Pending').count(),
        'today':Appointment.objects.filter(date=timezone.localdate()).count(),
        'received':sum((p.net for p in Payment.objects.prefetch_related('adjustments')),Decimal('0')),
        'outstanding':sum((i.balance for i in invoices),Decimal('0')),
        'staff_count':Staff.objects.filter(active=True).count(),
    })


@staff_only
@require_POST
def appointment_status(request,pk):
    get_object_or_404(Appointment,pk=pk)
    try: change_status(pk,request.POST.get('status'),request.user)
    except ValidationError as exc: messages.error(request,' '.join(exc.messages))
    else: messages.success(request,'Appointment updated.')
    return redirect('dashboard')


@staff_only
def staff_list(request):
    return render(request,'staff_list.html',{'people':Staff.objects.prefetch_related('services'),'leaves':StaffLeave.objects.select_related('staff').filter(date__gte=timezone.localdate()).order_by('date')})


@staff_only
def staff_edit(request,pk=None):
    person=get_object_or_404(Staff,pk=pk) if pk else None
    form=StaffForm(request.POST if request.method=='POST' else None,instance=person)
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            lock_schedule()
            # Avoid invalidating appointments when hours, skills or active status change.
            if person and Appointment.objects.filter(staff=person,status__in=ACTIVE,date__gte=timezone.localdate()).exists():
                form.add_error(None,'Resolve upcoming pending/approved bookings before changing this staff record.')
            else:
                person=form.save();audit(request.user,'Staff saved',f'Staff #{person.pk}');messages.success(request,'Staff member saved.');return redirect('staff_list')
    return render(request,'edit_form.html',{'form':form,'title':'Edit staff member' if pk else 'Add staff member'})


@staff_only
def leave_add(request):
    form=LeaveForm(request.POST if request.method=='POST' else None)
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            lock_schedule()
            if Appointment.objects.filter(staff=form.cleaned_data['staff'],date=form.cleaned_data['date'],status__in=ACTIVE).exists():
                form.add_error(None,'Resolve this staff member’s bookings for that date before adding leave.')
            else: item=form.save();audit(request.user,'Staff leave added',f'Leave #{item.pk}');messages.success(request,'Leave added.');return redirect('staff_list')
    return render(request,'edit_form.html',{'form':form,'title':'Add staff leave'})


@staff_only
@require_POST
def leave_delete(request,pk):
    with transaction.atomic():
        lock_schedule();get_object_or_404(StaffLeave,pk=pk).delete();audit(request.user,'Staff leave removed',f'Leave #{pk}')
    return redirect('staff_list')


@staff_only
def service_manage(request,pk=None):
    service=get_object_or_404(Service,pk=pk) if pk else None
    form=ServiceForm(request.POST if request.method=='POST' else None,request.FILES or None,instance=service)
    if request.method=='POST' and form.is_valid():
        service=form.save();audit(request.user,'Service saved',f'Service #{service.pk}');messages.success(request,'Service saved.');return redirect('service_list')
    return render(request,'edit_form.html',{'form':form,'title':'Edit service' if pk else 'Add service'})


@staff_only
def service_list(request):
    return render(request,'service_manage.html',{'services':Service.objects.all()})


@staff_only
def inbox(request):
    return render(request,'inbox.html',{'items':ContactMessage.objects.order_by('-created_at')[:100]})


@staff_only
def invoice_create(request,pk):
    a=get_object_or_404(Appointment,pk=pk)
    if Invoice.objects.filter(appointment=a).exists(): return redirect('invoice_detail',pk=a.invoice.pk)
    form=InvoiceForm(request.POST if request.method=='POST' else None)
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            lock_schedule()
            a=Appointment.objects.select_related('service').get(pk=pk)
            subtotal=a.quoted_price if a.quoted_price is not None else a.service.price
            if a.status!='Completed': form.add_error(None,'Complete the appointment before creating its bill.')
            elif form.cleaned_data['discount']>subtotal: form.add_error('discount','Discount cannot exceed the service price.')
            else:
                invoice,_=Invoice.objects.get_or_create(appointment=a,defaults={'service_name':a.treatment,'subtotal':subtotal,'discount':form.cleaned_data['discount']})
                audit(request.user,'Bill created',f'Bill #{invoice.pk} for appointment #{a.pk}')
                notify(a.user,f'Your bill #{invoice.pk} is ready.',reverse('invoice_detail',args=[invoice.pk]))
                return redirect('invoice_detail',pk=invoice.pk)
    return render(request,'edit_form.html',{'form':form,'title':f'Create bill for appointment #{a.pk}'})


@login_required
def invoice_detail(request,pk):
    invoice=get_object_or_404(Invoice.objects.select_related('appointment').prefetch_related('payments'),pk=pk)
    if not manager(request.user) and invoice.appointment.user_id!=request.user.pk: raise PermissionDenied
    form=PaymentForm(initial={'token':uuid4(),'amount':invoice.balance})
    if request.method=='POST':
        if not manager(request.user): raise PermissionDenied
        form=PaymentForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                # Lock invoice before reading balance; also serializes SQLite writers.
                Invoice.objects.filter(pk=pk).update(discount=F('discount'))
                invoice=Invoice.objects.select_for_update().get(pk=pk)
                data=form.cleaned_data
                if Payment.objects.filter(token=data['token']).exists():
                    messages.info(request,'This payment submission has already been recorded.')
                    return redirect('invoice_detail',pk=pk)
                if data['amount']>invoice.balance: form.add_error('amount','Amount cannot exceed the unpaid balance.')
                else:
                    payment=Payment.objects.create(invoice=invoice,recorded_by=request.user,**data)
                    audit(request.user,'Payment recorded',f'Payment #{payment.pk}, bill #{invoice.pk}, amount {payment.amount}')
                    notify(invoice.appointment.user,f'Payment of ₹{payment.amount} recorded for bill #{invoice.pk}.',reverse('invoice_detail',args=[invoice.pk]))
                    messages.success(request,'Payment recorded.');return redirect('invoice_detail',pk=pk)
    return render(request,'invoice.html',{'invoice':invoice,'form':form})
