import csv
from collections import defaultdict
from datetime import date,datetime,time,timedelta
from decimal import Decimal
from uuid import uuid4
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied,ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F,Q,Sum,Count
from django.http import HttpResponse,FileResponse
from django.shortcuts import render,redirect,get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import *
from .access import manager_only,manager,employee
from .events import audit,notify
from .extra_forms import *
from .forms import AppointmentForm
from .scheduling import ACTIVE,lock_schedule,save_booking


def form_page(request,form,title,**context):
    return render(request,'customer_form.html',{'form':form,'title':title,**context})


@login_required
def notifications(request):
    items=Notification.objects.filter(user=request.user).order_by('-created_at')
    if request.method=='POST':
        items.filter(read=False).update(read=True)
        return redirect('notifications')
    return render(request,'notifications.html',{'page':Paginator(items,30).get_page(request.GET.get('page'))})


@login_required
def waitlist(request):
    form=WaitlistForm(request.POST if request.method=='POST' else None)
    if request.method=='POST' and form.is_valid():
        item=form.save(commit=False);item.user=request.user
        if not WaitlistEntry.objects.filter(user=request.user,service=item.service,date=item.date,status__in=['Waiting','Offered']).exists():
            item.save();audit(request.user,'Joined waitlist',f'Entry #{item.pk}')
        messages.success(request,'You are on the waiting list. An offer does not reserve a slot; you still need to book.')
        return redirect('waitlist')
    return render(request,'waitlist.html',{'form':form,'items':WaitlistEntry.objects.filter(user=request.user).select_related('service').order_by('-date')})


@manager_only
def waitlist_manage(request):
    return render(request,'waitlist_manage.html',{'items':WaitlistEntry.objects.filter(status__in=['Waiting','Offered'],date__gte=timezone.localdate()).select_related('user','service').order_by('date','created_at')})


@login_required
@require_POST
def waitlist_action(request,pk):
    item=get_object_or_404(WaitlistEntry,pk=pk)
    action=request.POST.get('action')
    if not manager(request.user) and (item.user_id!=request.user.pk or action!='Closed'):raise PermissionDenied
    if action not in ['Offered','Closed']: raise PermissionDenied
    with transaction.atomic():
        lock_schedule();item=WaitlistEntry.objects.get(pk=pk)
        if item.status in ['Booked','Closed']:return redirect('waitlist_manage' if manager(request.user) else 'waitlist')
        if action=='Offered':
            from .scheduling import slots
            if not any(slots(s,item.service,item.date,user=item.user) for s in Staff.objects.filter(active=True,services=item.service)):
                messages.error(request,'No suitable slot is available for this request yet.');return redirect('waitlist_manage')
            if item.status!='Offered':notify(item.user,f'A slot is available for {item.service.name} on {item.date}. Book while it remains available.',reverse('booking')+f'?service={item.service_id}&date={item.date}')
        item.status=action;item.save();audit(request.user,'Waitlist updated',f'Entry #{item.pk}: {action}')
    return redirect('waitlist_manage' if manager(request.user) else 'waitlist')


@login_required
def review(request,pk):
    a=get_object_or_404(Appointment,pk=pk,user=request.user,status='Completed')
    instance=Review.objects.filter(appointment=a).first()
    form=ReviewForm(request.POST if request.method=='POST' else None,instance=instance)
    if request.method=='POST' and form.is_valid():
        item=form.save(commit=False);item.appointment=a;item.save()
        audit(request.user,'Review saved',f'Appointment #{a.pk}')
        messages.success(request,'Your review has been saved.');return redirect('profile')
    return form_page(request,form,'Review your completed appointment')


def reviews(request):
    items=Review.objects.filter(visible=True).select_related('appointment__service').order_by('-created_at')
    return render(request,'reviews.html',{'page':Paginator(items,20).get_page(request.GET.get('page'))})


@manager_only
def package_edit(request,pk=None):
    instance=get_object_or_404(Package,pk=pk) if pk else None
    form=PackageForm(request.POST if request.method=='POST' else None,instance=instance)
    if request.method=='POST' and form.is_valid():
        item=form.save();audit(request.user,'Package saved',f'Package #{item.pk}');return redirect('packages')
    return form_page(request,form,'Edit package' if pk else 'Create package / offer')


def packages(request):
    items=Package.objects.prefetch_related('services').all() if manager(request.user) else Package.objects.filter(active=True).filter(Q(valid_until__isnull=True)|Q(valid_until__gte=timezone.localdate())).prefetch_related('services')
    rows=[{'item':x,'total':sum((s.price for s in x.services.all()),Decimal('0'))-x.discount,'duration':sum(s.duration for s in x.services.all())} for x in items]
    return render(request,'packages.html',{'rows':rows})


@manager_only
def inventory(request):
    return render(request,'inventory.html',{'items':Product.objects.order_by('name'),'movements':StockMovement.objects.select_related('product','actor').order_by('-created_at')[:50]})


@manager_only
def product_edit(request,pk=None):
    form=ProductForm(request.POST if request.method=='POST' else None,instance=get_object_or_404(Product,pk=pk) if pk else None)
    if request.method=='POST' and form.is_valid():
        product=form.save();audit(request.user,'Product saved',f'Product #{product.pk}');return redirect('inventory')
    return form_page(request,form,'Product details (stock is recorded separately)')


@manager_only
def stock_change(request,pk):
    product=get_object_or_404(Product,pk=pk)
    form=StockForm(request.POST if request.method=='POST' else None,initial={'token':uuid4()})
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            Product.objects.filter(pk=pk).update(stock=F('stock'));product=Product.objects.select_for_update().get(pk=pk)
            if StockMovement.objects.filter(token=form.cleaned_data['token']).exists():return redirect('inventory')
            new=product.stock+form.cleaned_data['quantity']
            if new<0 or new>Decimal('99999999.99'):form.add_error('quantity','Stock must stay between zero and 99,999,999.99.')
            else:
                product.stock=new;product.save(update_fields=['stock'])
                StockMovement.objects.create(product=product,actor=request.user,**form.cleaned_data)
                audit(request.user,'Stock changed',f'{product.name}: {form.cleaned_data["quantity"]} {product.unit}; {form.cleaned_data["reason"]}')
                return redirect('inventory')
    return form_page(request,form,f'Receive / use stock: {product.name} (available {product.stock} {product.unit})')


@manager_only
def payment_adjust(request,pk):
    payment=get_object_or_404(Payment,pk=pk)
    form=AdjustmentForm(request.POST if request.method=='POST' else None,initial={'token':uuid4()})
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            Invoice.objects.filter(pk=payment.invoice_id).update(discount=F('discount'))
            payment=Payment.objects.select_for_update().get(pk=pk)
            if PaymentAdjustment.objects.filter(token=form.cleaned_data['token']).exists():return redirect('invoice_detail',pk=payment.invoice_id)
            if form.cleaned_data['amount']>payment.net:form.add_error('amount','This exceeds the unadjusted amount of the original payment.')
            else:
                adjustment=PaymentAdjustment.objects.create(payment=payment,actor=request.user,**form.cleaned_data)
                audit(request.user,'Payment '+adjustment.kind.lower(),f'Payment #{pk}, amount {adjustment.amount}, reason: {adjustment.reason}')
                notify(payment.invoice.appointment.user,f'Bill #{payment.invoice_id}: {adjustment.kind.lower()} of ₹{adjustment.amount} recorded.',reverse('invoice_detail',args=[payment.invoice_id]))
                return redirect('invoice_detail',pk=payment.invoice_id)
    return form_page(request,form,f'Adjust payment #{payment.pk}',description='A correction reverses a mistaken entry and reopens the unpaid balance. A refund records money already returned and credits the bill by the same amount. Neither operation moves money.')


@manager_only
def block_add(request):
    form=BlockForm(request.POST if request.method=='POST' else None)
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            lock_schedule();d=form.cleaned_data
            appointments=Appointment.objects.filter(date=d['date'],status__in=ACTIVE).select_related('service')
            if d['staff']:appointments=appointments.filter(staff=d['staff'])
            start=d['start_time'].hour*60+d['start_time'].minute;end=d['end_time'].hour*60+d['end_time'].minute
            clash=any(start<a.time.hour*60+a.time.minute+(a.duration_minutes or a.service.duration) and end>a.time.hour*60+a.time.minute for a in appointments)
            if clash:form.add_error(None,'Resolve overlapping appointments before blocking this time.')
            else:
                item=form.save();audit(request.user,'Schedule blocked',f'Block #{item.pk}: {item.reason}');return redirect('blocks')
    return form_page(request,form,'Add break / holiday / closure')


@manager_only
def blocks(request):
    return render(request,'blocks.html',{'items':ScheduleBlock.objects.filter(date__gte=timezone.localdate()).select_related('staff').order_by('date','start_time')})


@manager_only
@require_POST
def block_delete(request,pk):
    with transaction.atomic():
        lock_schedule();item=get_object_or_404(ScheduleBlock,pk=pk);item.delete();audit(request.user,'Schedule block removed',f'Block #{pk}')
    return redirect('blocks')


@manager_only
def salon_settings(request):
    original=SalonSettings.current()
    form=SettingsForm(request.POST if request.method=='POST' else None,instance=original)
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            lock_schedule()
            if any(x in form.changed_data for x in ['weekday_open','weekday_close','sunday_open','sunday_close']) and Appointment.objects.filter(status__in=ACTIVE,date__gte=timezone.localdate()).exists():
                form.add_error(None,'Resolve upcoming active bookings before changing salon opening hours.')
            else:
                config=form.save(commit=False);config.pk=1;config.save();audit(request.user,'Salon settings updated',', '.join(form.changed_data));return redirect('dashboard')
    return form_page(request,form,'Salon settings')


@manager_only
def staff_account(request,pk):
    person=get_object_or_404(Staff,pk=pk)
    if person.user_id:
        messages.info(request,'This beautician already has a login. Use password reset to recover access.');return redirect('staff_list')
    form=StaffAccountForm(request.POST if request.method=='POST' else None)
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            lock_schedule();person=Staff.objects.get(pk=pk)
            if person.user_id:return redirect('staff_list')
            person.user=User.objects.create_user(**form.cleaned_data);person.save(update_fields=['user'])
            audit(request.user,'Beautician login created',f'Staff #{pk}')
        messages.success(request,'Beautician login created. They can view only their own schedule.');return redirect('staff_list')
    return form_page(request,form,f'Create login for {person.name}')


@login_required
def calendar(request):
    person=employee(request.user)
    if not manager(request.user) and not person:raise PermissionDenied
    try:day=date.fromisoformat(request.GET.get('date',''))
    except ValueError:day=timezone.localdate()
    weekly=request.GET.get('view')=='week';start=day-timedelta(days=day.weekday()) if weekly else day
    end=start+timedelta(days=6 if weekly else 0)
    query=Appointment.objects.filter(date__range=(start,end)).select_related('staff','service').order_by('date','time')
    if not manager(request.user):query=query.filter(staff=person)
    selected=request.GET.get('staff','')
    if manager(request.user) and selected.isdigit():query=query.filter(staff_id=int(selected))
    days=[{'date':start+timedelta(days=i),'appointments':[]} for i in range(7 if weekly else 1)]
    for a in query:days[(a.date-start).days]['appointments'].append(a)
    return render(request,'calendar.html',{'days':days,'day':day.isoformat(),'weekly':weekly,'people':Staff.objects.filter(active=True),'selected_staff':selected})


@manager_only
def walk_in(request,pk=None):
    existing=get_object_or_404(Appointment,pk=pk) if pk else None
    initial={}
    user=None
    user_id=existing.user_id if existing else (request.GET.get('customer') or request.POST.get('customer'))
    if user_id:
        user=get_object_or_404(User,pk=user_id)
        profile=getattr(user,'userprofile',None)
        initial={'name':user.get_full_name() or user.username,'email':user.email,'phone':profile.phone if profile else ''}
    form=AppointmentForm(request.POST if request.method=='POST' else None,initial=None if existing else initial,instance=existing,user=user)
    form.fields['email'].required=False
    if request.method=='POST' and form.is_valid():
        try:save_booking(form,user,appointment_id=pk,actor=request.user,walk_in=True)
        except ValidationError as exc:form.add_error(None,exc)
        else:messages.success(request,'Reception booking confirmed.');return redirect('dashboard')
    return render(request,'booking.html',{'form':form,'walk_in':True,'customer':user,'appointment':existing,'rescheduling':bool(existing)})


@manager_only
def customers(request):
    q=request.GET.get('q','').strip()
    people=User.objects.filter(Q(appointments__isnull=False)|Q(userprofile__isnull=False)).distinct().order_by('username')
    if q:people=people.filter(Q(username__icontains=q)|Q(first_name__icontains=q)|Q(last_name__icontains=q)|Q(userprofile__phone__icontains=q)|Q(email__icontains=q))
    walkins=Appointment.objects.filter(user__isnull=True)
    if q:walkins=walkins.filter(Q(name__icontains=q)|Q(phone__icontains=q))
    return render(request,'customers.html',{'q':q,'page':Paginator(people,20).get_page(request.GET.get('page')),'walkins':walkins.order_by('-date')[:30]})


@manager_only
def customer_detail(request,pk):
    person=get_object_or_404(User,pk=pk)
    appointments=Appointment.objects.filter(user=person).select_related('service','staff').order_by('-date')
    return render(request,'customer_detail.html',{'person':person,'page':Paginator(appointments,30).get_page(request.GET.get('page'))})


@manager_only
def activity(request):
    return render(request,'activity.html',{'page':Paginator(AuditEvent.objects.select_related('actor').order_by('-created_at'),50).get_page(request.GET.get('page'))})


def csv_value(value):
    value=str(value)
    return "'"+value if value.lstrip().startswith(('=','+','-','@')) else value


@manager_only
def reports(request):
    try:
        month=request.GET.get('month',timezone.localdate().strftime('%Y-%m'))
        start=date.fromisoformat(month+'-01')
        if not 1900<=start.year<=9998:raise ValueError('Unsupported year')
    except ValueError:
        messages.error(request,'Choose a valid month.');return redirect('reports')
    end=(start.replace(day=28)+timedelta(days=4)).replace(day=1)
    payments=list(Payment.objects.filter(created_at__date__gte=start,created_at__date__lt=end).select_related('invoice'))
    changes=list(PaymentAdjustment.objects.filter(created_at__date__gte=start,created_at__date__lt=end).select_related('payment'))
    received=sum((x.amount for x in payments),Decimal('0'))
    adjustments=sum((x.amount for x in changes),Decimal('0'))
    appointments=Appointment.objects.filter(date__gte=start,date__lt=end)
    status=list(appointments.values('status').annotate(count=Count('id')).order_by('status'))
    popular=list(AppointmentItem.objects.filter(appointment__in=appointments,appointment__status='Completed').values('name').annotate(count=Count('id')).order_by('-count')[:10])
    methods={x:Decimal('0') for x in ['Cash','UPI','Card']}
    daily=defaultdict(lambda:Decimal('0'))
    for x in payments:methods[x.method]+=x.amount;daily[timezone.localtime(x.created_at).date().isoformat()]+=x.amount
    for x in changes:methods[x.payment.method]-=x.amount;daily[timezone.localtime(x.created_at).date().isoformat()]-=x.amount
    if request.GET.get('export')=='csv':
        response=HttpResponse(content_type='text/csv');response['Content-Disposition']=f'attachment; filename="salon_report_{month}.csv"'
        writer=csv.writer(response);writer.writerow(['Date','Record type','Record ID','Bill','Method','Amount','Note'])
        for x in payments:writer.writerow([x.created_at.isoformat(),'Payment',x.pk,x.invoice_id,x.method,x.amount,csv_value(x.reference)])
        for x in changes:writer.writerow([x.created_at.isoformat(),x.kind,x.pk,x.payment.invoice_id,x.payment.method,-x.amount,csv_value(x.reason)])
        return response
    balances=sum((i.balance for i in Invoice.objects.prefetch_related('payments__adjustments')),Decimal('0'))
    maximum=max([x['count'] for x in popular] or [1])
    for x in popular:x['width']=x['count']/maximum*100
    return render(request,'reports.html',{'month':month,'received':received,'adjustments':adjustments,'net':received-adjustments,'outstanding':balances,'statuses':status,'popular':popular,'methods':methods.items(),'daily':sorted(daily.items())})


@manager_only
def backups(request):
    if not request.user.is_superuser:raise PermissionDenied
    if request.method=='POST':
        from .backup import create_backup
        path=create_backup()
        audit(request.user,'Backup downloaded','Database and uploaded media archive')
        # Delete the temporary archive after streaming; the downloaded copy is the backup.
        import tempfile,shutil
        handle=tempfile.TemporaryFile()
        with open(path,'rb') as source:shutil.copyfileobj(source,handle)
        path.unlink();handle.seek(0)
        return FileResponse(handle,as_attachment=True,filename='Beauty_Parlour_Backup_'+timezone.now().strftime('%Y%m%d_%H%M%S')+'.zip')
    return render(request,'backups.html')
