from datetime import datetime,timedelta
from decimal import Decimal
from io import StringIO
from uuid import uuid4
from unittest.mock import patch
from django.test import TestCase,override_settings,Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from django.core.management import call_command
from django.core import mail
from .models import *

class CompleteUpdateTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('client','client@example.com','Good-password-941!')
        self.admin=User.objects.create_user('owner','owner@example.com','Good-password-941!',is_staff=True,is_superuser=True)
        self.worker=User.objects.create_user('beautician','worker@example.com','Good-password-941!')
        self.service=Service.objects.create(name='Hair Spa',price=100,duration=60,description='Care',image='services/Hair_Spa.jpg')
        self.extra=Service.objects.create(name='Facial',price=200,duration=45,description='Care',image='services/Facial_Treatment.jpg')
        self.staff=Staff.objects.create(name='Beautician',user=self.worker)
        self.staff.services.set([self.service,self.extra])
        self.day=timezone.localdate()+timedelta(days=3)
        self.data={'name':'Client','email':'client@example.com','phone':'9123456789','service':self.service.pk,'staff':self.staff.pk,'date':self.day.isoformat(),'time':'11:00'}
        self.client.force_login(self.user)

    def book(self,**changes):
        response=self.client.post(reverse('booking'),{**self.data,**changes})
        self.assertEqual(response.status_code,302,response.content[:500])
        return Appointment.objects.latest('pk')

    def invoice(self):
        a=self.book();a.status='Completed';a.save()
        return Invoice.objects.create(appointment=a,service_name='Hair Spa',subtotal=100)

    def test_customer_profile_and_duplicate_contact_validation(self):
        response=self.client.post(reverse('edit_profile'),{'first_name':'Aneta','last_name':'Baby','email':'new@example.com','phone':'9876543210'})
        self.assertEqual(response.status_code,302)
        self.user.refresh_from_db();self.assertEqual(self.user.first_name,'Aneta')
        self.assertEqual(self.user.userprofile.phone,'9876543210')
        response=self.client.post(reverse('edit_profile'),{'first_name':'Aneta','last_name':'Baby','email':'owner@example.com','phone':'9876543210'})
        self.assertContains(response,'Email is already used.')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_password_reset_generates_email_without_enumeration(self):
        self.client.logout()
        self.assertEqual(self.client.post(reverse('password_reset'),{'email':self.user.email}).status_code,302)
        self.assertEqual(len(mail.outbox),1);self.assertIn('/accounts/reset/',mail.outbox[0].body)
        self.assertEqual(self.client.post(reverse('password_reset'),{'email':'missing@example.com'}).status_code,302)
        self.assertEqual(len(mail.outbox),1)

    def test_multiple_services_snapshot_duration_price_and_skills(self):
        a=self.book(extras=[self.extra.pk])
        self.assertEqual(a.duration_minutes,105);self.assertEqual(a.quoted_price,300)
        self.assertEqual(a.reservations.count(),105);self.assertEqual(a.items.count(),2)
        self.assertIn('Facial',a.treatment)
        self.client.post(reverse('cancel_booking',args=[a.pk]))
        self.staff.services.remove(self.extra)
        self.assertEqual(self.client.post(reverse('booking'),{**self.data,'extras':[self.extra.pk]}).status_code,200)
        self.assertEqual(Appointment.objects.count(),1)

    def test_package_discount_expiry_and_snapshot_reschedule(self):
        package=Package.objects.create(name='Glow',discount=50,valid_until=self.day)
        package.services.set([self.service,self.extra])
        a=self.book(service='',package=package.pk)
        self.assertEqual(a.quoted_price,250);self.assertEqual(a.duration_minutes,105)
        package.active=False;package.save()
        response=self.client.post(reverse('reschedule',args=[a.pk]),{**self.data,'time':'14:00'})
        self.assertEqual(response.status_code,302,response.content[:500])
        a.refresh_from_db();self.assertEqual(a.quoted_price,250);self.assertEqual(a.items.count(),2)
        package.active=True;package.valid_until=self.day-timedelta(days=1);package.save()
        self.assertEqual(self.client.post(reverse('booking'),{**self.data,'package':package.pk}).status_code,200)

    def test_employee_only_sees_assigned_appointments_and_no_finances(self):
        a=self.book()
        other_staff=Staff.objects.create(name='Another');other_staff.services.add(self.service)
        Appointment.objects.create(user=self.user,staff=other_staff,name='Hidden customer',email='',phone='9123456789',service=self.service,date=self.day,time='15:00')
        self.client.force_login(self.worker)
        self.assertContains(self.client.get(reverse('dashboard')),'Hair Spa')
        self.assertNotContains(self.client.get(reverse('dashboard')),'Hidden customer')
        self.assertNotContains(self.client.get(reverse('calendar'),{'date':self.day.isoformat()}),'Hidden customer')
        for name in ['reports','customers','inventory','staff_list','salon_settings','activity','backups']:
            self.assertEqual(self.client.get(reverse(name)).status_code,403)
        invoice=Invoice.objects.create(appointment=a,service_name='Spa',subtotal=100)
        self.assertEqual(self.client.get(reverse('invoice_detail',args=[invoice.pk])).status_code,403)

    def test_break_closure_and_notice_policy(self):
        self.client.force_login(self.admin)
        response=self.client.post(reverse('block_add'),{'staff':self.staff.pk,'date':self.day,'start_time':'10:30','end_time':'11:30','reason':'Lunch'})
        self.assertEqual(response.status_code,302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(reverse('booking'),self.data).status_code,200)
        ScheduleBlock.objects.all().delete()
        a=self.book()
        config=SalonSettings.current();config.change_notice_hours=200;config.save()
        self.client.post(reverse('cancel_booking',args=[a.pk]))
        a.refresh_from_db();self.assertEqual(a.status,'Pending')
        self.assertEqual(self.client.post(reverse('reschedule',args=[a.pk]),{**self.data,'time':'14:00'}).status_code,200)

    def test_reception_guest_and_existing_customer(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(reverse('walk_in'),{**self.data,'email':''}).status_code,302)
        a=Appointment.objects.get();self.assertIsNone(a.user_id);self.assertTrue(a.walk_in);self.assertEqual(a.status,'Approved')
        self.assertEqual(self.client.post(reverse('walk_in'),{**self.data,'time':'13:00','customer':self.user.pk}).status_code,302)
        self.assertEqual(Appointment.objects.latest('pk').user,self.user)
        self.assertContains(self.client.get(reverse('customers'),{'q':'9123456789'}),'Client')

    def test_waitlist_offer_close_and_booking(self):
        self.client.post(reverse('waitlist'),{'service':self.service.pk,'date':self.day,'notes':'Morning'})
        entry=WaitlistEntry.objects.get()
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(reverse('waitlist_action',args=[entry.pk]),{'action':'Offered'}).status_code,302)
        entry.refresh_from_db();self.assertEqual(entry.status,'Offered')
        self.assertTrue(Notification.objects.filter(user=self.user,text__contains='slot is available').exists())
        self.client.force_login(self.user);self.book()
        entry.refresh_from_db();self.assertEqual(entry.status,'Booked')

    def test_review_requires_own_completed_appointment(self):
        a=self.book()
        self.assertEqual(self.client.post(reverse('review',args=[a.pk]),{'rating':5,'comment':'Great'}).status_code,404)
        a.status='Completed';a.save()
        self.assertEqual(self.client.post(reverse('review',args=[a.pk]),{'rating':5,'comment':'Great'}).status_code,302)
        self.assertEqual(Review.objects.count(),1)
        self.assertContains(self.client.get(reverse('reviews')),'Great')
        self.client.force_login(self.worker)
        self.assertEqual(self.client.get(reverse('review',args=[a.pk])).status_code,404)

    def test_payment_correction_refund_and_double_submission(self):
        invoice=self.invoice()
        self.client.force_login(self.admin)
        payment=Payment.objects.create(invoice=invoice,amount=100,method='Cash',recorded_by=self.admin,token=uuid4())
        url=reverse('payment_adjust',args=[payment.pk])
        correction={'kind':'Correction','amount':'20','reason':'Entered too much','token':str(uuid4())}
        self.assertEqual(self.client.post(url,correction).status_code,302)
        self.client.post(url,correction)
        self.assertEqual(PaymentAdjustment.objects.count(),1)
        self.assertEqual(invoice.paid,80);self.assertEqual(invoice.balance,20)
        self.assertEqual(self.client.post(url,{'kind':'Refund','amount':'30','reason':'Goodwill','token':str(uuid4())}).status_code,302)
        self.assertEqual(invoice.total,70);self.assertEqual(invoice.paid,50);self.assertEqual(invoice.balance,20)
        self.assertEqual(self.client.post(url,{'kind':'Refund','amount':'51','reason':'Too much','token':str(uuid4())}).status_code,200)
        self.assertEqual(PaymentAdjustment.objects.count(),2)
        self.client.force_login(self.user);self.assertEqual(self.client.post(url,correction).status_code,403)

    def test_stock_movements_low_stock_and_no_negative_balance(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('product_add'),{'name':'Shampoo','unit':'ml','low_stock':'20','active':'on'})
        product=Product.objects.get()
        data={'quantity':'100','reason':'Delivery','token':str(uuid4())}
        url=reverse('stock_change',args=[product.pk])
        self.client.post(url,data);self.client.post(url,data)
        product.refresh_from_db();self.assertEqual(product.stock,100);self.assertEqual(StockMovement.objects.count(),1)
        self.client.post(url,{'quantity':'-90','reason':'Used','token':str(uuid4())})
        self.assertContains(self.client.get(reverse('inventory')),'Low stock')
        self.client.post(url,{'quantity':'-11','reason':'Too much','token':str(uuid4())})
        product.refresh_from_db();self.assertEqual(product.stock,10)

    def test_reports_net_receipts_csv_and_access(self):
        invoice=self.invoice();self.client.force_login(self.admin)
        payment=Payment.objects.create(invoice=invoice,amount=100,method='UPI',reference='=unsafe()',recorded_by=self.admin,token=uuid4())
        PaymentAdjustment.objects.create(payment=payment,amount=25,kind='Refund',reason='Returned',actor=self.admin,token=uuid4())
        response=self.client.get(reverse('reports'))
        self.assertEqual(response.status_code,200);self.assertEqual(response.context['net'],75)
        csv=self.client.get(reverse('reports'),{'export':'csv'}).content.decode()
        self.assertIn("'=unsafe()",csv);self.assertIn('-25.00',csv)
        self.client.force_login(self.user);self.assertEqual(self.client.get(reverse('reports')).status_code,403)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_reminders_once_and_email_delivery(self):
        a=self.book();a.status='Approved';a.save()
        moment=timezone.make_aware(datetime.combine(a.date,a.time))-timedelta(hours=10)
        with patch('django.utils.timezone.now',return_value=moment):
            call_command('send_reminders',stdout=StringIO());call_command('send_reminders',stdout=StringIO())
        self.assertEqual(Notification.objects.filter(text__startswith='Reminder:').count(),1)
        call_command('send_notifications',stdout=StringIO())
        self.assertEqual(len(mail.outbox),2)
        call_command('send_notifications',stdout=StringIO());self.assertEqual(len(mail.outbox),2)

    def test_no_show_and_notification_ownership(self):
        a=self.book();a.status='Approved';a.save();self.client.force_login(self.admin)
        with patch('django.utils.timezone.now',return_value=timezone.make_aware(datetime.combine(a.date,a.time))+timedelta(minutes=5)):
            self.client.post(reverse('appointment_status',args=[a.pk]),{'status':'No-show'})
        a.refresh_from_db();self.assertEqual(a.status,'No-show');self.assertFalse(a.reservations.exists())
        Notification.objects.create(user=self.worker,text='Secret worker update')
        self.client.force_login(self.user)
        self.assertNotContains(self.client.get(reverse('notifications')),'Secret worker update')
        self.client.post(reverse('notifications'))
        self.assertFalse(Notification.objects.filter(user=self.user,read=False).exists())
        self.assertTrue(Notification.objects.filter(user=self.worker,read=False).exists())

    def test_staff_account_and_all_new_pages_render(self):
        self.client.force_login(self.admin)
        person=Staff.objects.create(name='New employee')
        response=self.client.post(reverse('staff_account',args=[person.pk]),{'username':'newemployee','email':'newemployee@example.com','password':'Good-password-9721!'})
        self.assertEqual(response.status_code,302)
        person.refresh_from_db();self.assertTrue(person.user.check_password('Good-password-9721!'));self.assertFalse(person.user.is_staff)
        for name in ['calendar','customers','inventory','reports','activity','salon_settings','blocks','block_add','package_add','packages','waitlist_manage','backups','walk_in','notifications','reviews','waitlist','product_add']:
            self.assertEqual(self.client.get(reverse(name)).status_code,200,name)
        self.assertEqual(self.client.get(reverse('customer_detail',args=[self.user.pk])).status_code,200)

    def test_post_actions_require_csrf(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.admin)
        self.assertEqual(client.post(reverse('product_add'),{'name':'Bad'}).status_code,403)

    def test_manager_assigns_legacy_booking_without_changing_owner(self):
        a=Appointment.objects.create(user=self.user,name='Client',email=self.user.email,phone='9123456789',service=self.service,date=self.day,time='11:00',quoted_price=80,duration_minutes=60)
        self.client.force_login(self.admin)
        response=self.client.get(reverse('manage_booking',args=[a.pk]))
        self.assertEqual(response.status_code,200)
        response=self.client.post(reverse('manage_booking',args=[a.pk]),{**self.data,'time':'12:00'})
        self.assertEqual(response.status_code,302)
        a.refresh_from_db();self.assertEqual(a.user,self.user);self.assertEqual(a.staff,self.staff);self.assertEqual(a.quoted_price,80);self.assertEqual(a.status,'Approved')
        self.assertEqual(a.reservations.count(),60)

    def test_linked_staff_flag_does_not_grant_manager_access(self):
        self.worker.is_staff=True;self.worker.save()
        self.client.force_login(self.worker)
        self.assertEqual(self.client.get(reverse('reports')).status_code,403)
        self.assertEqual(self.client.get(reverse('calendar')).status_code,200)


    def test_staff_deactivation_after_form_validation_blocks_booking(self):
        from .forms import AppointmentForm
        from .scheduling import save_booking
        from django.core.exceptions import ValidationError
        form=AppointmentForm(self.data,user=self.user)
        self.assertTrue(form.is_valid())
        Staff.objects.filter(pk=self.staff.pk).update(active=False)
        with self.assertRaises(ValidationError):save_booking(form,self.user)
        self.assertFalse(Appointment.objects.exists())


from django.test import SimpleTestCase
class BackupTests(SimpleTestCase):
    def test_backup_restore_and_reject_traversal(self):
        import tempfile,sqlite3,zipfile,json
        from pathlib import Path
        from salon.backup import create_backup,restore_backup
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);media=root/'media';media.mkdir();(media/'sample.txt').write_text('original image placeholder')
            db=root/'db.sqlite3'
            with sqlite3.connect(db) as conn:
                conn.executescript('CREATE TABLE django_migrations(id INTEGER); CREATE TABLE auth_user(id INTEGER); CREATE TABLE salon_appointment(id INTEGER); INSERT INTO salon_appointment VALUES(1);')
            with override_settings(BASE_DIR=root,MEDIA_ROOT=media,DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':str(db)}}):
                archive=create_backup(root/'saved.zip')
                with sqlite3.connect(db) as conn:conn.execute('DELETE FROM salon_appointment')
                (media/'sample.txt').write_text('changed')
                recovery=restore_backup(archive)
                self.assertTrue(recovery.exists())
                with sqlite3.connect(db) as conn:self.assertEqual(conn.execute('SELECT COUNT(*) FROM salon_appointment').fetchone()[0],1)
                self.assertEqual((media/'sample.txt').read_text(),'original image placeholder')
                with zipfile.ZipFile(root/'bad.zip','w') as z:z.writestr('../outside.txt','bad')
                with self.assertRaises(ValueError):restore_backup(root/'bad.zip')
                self.assertFalse((root.parent/'outside.txt').exists())
