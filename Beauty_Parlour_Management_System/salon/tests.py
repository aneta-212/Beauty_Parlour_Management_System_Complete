from datetime import timedelta
from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from .models import Appointment, Service, ContactMessage, Staff, StaffLeave, Reservation, Invoice, Payment

class WorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('customer', 'customer@example.com', 'Test-pass-284!')
        self.service = Service.objects.create(name='Hair Spa', description='Care', price=999, duration=60, image='services/Hair_Spa.jpg')
        self.staff = Staff.objects.create(name='Test Beautician')
        self.staff.services.add(self.service)
        self.data = dict(staff=self.staff.pk, name='Different display name', email='customer@example.com', phone='9876543210', service=self.service.pk, date=(timezone.localdate()+timedelta(days=2)).isoformat(), time='11:00', notes='Test')

    def test_public_pages_render(self):
        self.client.logout()
        for name in ['home', 'services', 'about', 'gallery', 'contact', 'register', 'login']:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_registration_and_phone_login(self):
        self.client.logout()
        response = self.client.post(reverse('register'), dict(username='newuser', email='new@example.com', phone='9123456789', password1='Strong-pass-839!', password2='Strong-pass-839!'))
        self.assertRedirects(response, reverse('profile'))
        self.assertEqual(User.objects.get(username='newuser').userprofile.phone, '9123456789')
        self.client.logout()
        self.assertRedirects(self.client.post(reverse('login'), {'login':'9123456789','password':'Strong-pass-839!'}), reverse('profile'))

    def test_booking_and_account_isolation(self):
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse('booking')), 'name="service"')
        self.assertRedirects(self.client.post(reverse('booking'), self.data), reverse('profile'))
        self.assertEqual(Appointment.objects.get().user, self.user)
        self.assertContains(self.client.get(reverse('profile')), 'Hair Spa')
        self.client.post(reverse('booking'), self.data)
        self.assertEqual(Appointment.objects.count(), 1)
        other = User.objects.create_user('other')
        self.client.force_login(other)
        self.assertNotContains(self.client.get(reverse('profile')), 'Hair Spa')

    def test_invalid_booking_is_rejected(self):
        self.client.force_login(self.user)
        for changes in [dict(date='2020-01-01'),dict(service=9999),dict(time='23:00'),dict(phone='abc')]:
            self.assertEqual(self.client.post(reverse('booking'), {**self.data, **changes}).status_code, 200)
        self.assertFalse(Appointment.objects.exists())

    def test_staff_access_and_logout(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 403)
        self.user.is_staff = True
        self.user.save()
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 200)
        self.assertEqual(self.client.get(reverse('logout')).status_code, 405)
        self.assertRedirects(self.client.post(reverse('logout')), reverse('home'))

    def test_login_next_is_safe(self):
        self.client.logout()
        response = self.client.post(reverse('login'), dict(login='customer@example.com', password='Test-pass-284!', next='https://example.com/'))
        self.assertRedirects(response, reverse('profile'))

    def test_contact_message_is_saved(self):
        self.assertRedirects(self.client.post(reverse('contact'), dict(name='Visitor', email='visitor@example.com', phone='', message='Please call me')), reverse('contact'))
        self.assertEqual(ContactMessage.objects.count(), 1)


class AdvancedWorkflowTests(WorkflowTests):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.admin = User.objects.create_user('manager',is_staff=True)

    def book(self):
        response=self.client.post(reverse('booking'),self.data)
        self.assertEqual(response.status_code,302)
        return Appointment.objects.latest('pk')

    def test_overlapping_bookings_are_blocked_and_cancel_releases(self):
        a=self.book()
        self.assertEqual(Reservation.objects.filter(appointment=a).count(),60)
        other=User.objects.create_user('second')
        self.client.force_login(other)
        self.assertEqual(self.client.post(reverse('booking'),{**self.data,'time':'11:15'}).status_code,200)
        self.assertEqual(Appointment.objects.count(),1)
        self.client.force_login(self.user)
        self.client.post(reverse('cancel_booking',args=[a.pk]))
        a.refresh_from_db();self.assertEqual(a.status,'Cancelled')
        self.assertFalse(a.reservations.exists())
        self.client.force_login(other)
        self.assertEqual(self.client.post(reverse('booking'),self.data).status_code,302)

    def test_reschedule_releases_old_time_and_keeps_price(self):
        a=self.book()
        self.service.price=2000;self.service.duration=90;self.service.save()
        self.assertEqual(self.client.post(reverse('reschedule',args=[a.pk]),{**self.data,'time':'13:00'}).status_code,302)
        a.refresh_from_db()
        self.assertEqual(a.time.hour,13);self.assertEqual(a.quoted_price,999)
        self.assertEqual(a.duration_minutes,60);self.assertEqual(a.status,'Pending')
        self.assertFalse(a.reservations.filter(minute__lt=13*60).exists())

    def test_customer_cannot_change_another_booking(self):
        a=self.book();self.client.force_login(User.objects.create_user('intruder'))
        self.assertEqual(self.client.post(reverse('cancel_booking',args=[a.pk])).status_code,404)
        self.assertEqual(self.client.get(reverse('reschedule',args=[a.pk])).status_code,404)
        self.assertEqual(self.client.post(reverse('appointment_status',args=[a.pk]),{'status':'Approved'}).status_code,403)

    def test_leave_hours_and_skill_restrictions(self):
        StaffLeave.objects.create(staff=self.staff,date=self.data['date'])
        self.assertEqual(self.client.post(reverse('booking'),self.data).status_code,200)
        StaffLeave.objects.all().delete()
        self.staff.services.clear()
        self.assertEqual(self.client.post(reverse('booking'),self.data).status_code,200)
        self.assertFalse(Appointment.objects.exists())

    def test_slot_api_excludes_reserved_times(self):
        self.book()
        response=self.client.get(reverse('available_slots'),{'service':self.service.pk,'staff':self.staff.pk,'date':self.data['date']})
        self.assertEqual(response.status_code,200)
        self.assertNotIn('11:00',response.json()['slots'])
        self.assertNotIn('11:15',response.json()['slots'])
        self.assertIn('12:00',response.json()['slots'])

    def test_staff_pages_and_leave_conflicts(self):
        self.book();self.client.force_login(self.admin)
        for name in ['dashboard','staff_list','staff_add','leave_add','service_list','service_add','inbox']:
            self.assertEqual(self.client.get(reverse(name)).status_code,200)
        self.assertEqual(self.client.get(reverse('staff_edit',args=[self.staff.pk])).status_code,200)
        self.assertEqual(self.client.get(reverse('service_edit',args=[self.service.pk])).status_code,200)
        self.client.post(reverse('leave_add'),{'staff':self.staff.pk,'date':self.data['date'],'reason':'Leave'})
        self.assertFalse(StaffLeave.objects.exists())

    def test_completed_appointment_billing_and_payments(self):
        from unittest.mock import patch
        from datetime import datetime, timedelta
        from uuid import uuid4
        a=self.book();self.client.force_login(self.admin)
        self.client.post(reverse('appointment_status',args=[a.pk]),{'status':'Approved'})
        a.refresh_from_db();self.assertEqual(a.status,'Approved')
        self.client.post(reverse('appointment_status',args=[a.pk]),{'status':'Completed'})
        a.refresh_from_db();self.assertEqual(a.status,'Approved')
        later=timezone.make_aware(datetime.combine(a.date,a.time))+timedelta(hours=2)
        with patch('salon.scheduling.timezone.now',return_value=later):
            self.client.post(reverse('appointment_status',args=[a.pk]),{'status':'Completed'})
        a.refresh_from_db();self.assertEqual(a.status,'Completed')
        self.client.post(reverse('invoice_create',args=[a.pk]),{'discount':'1000'})
        self.assertFalse(Invoice.objects.exists())
        self.client.post(reverse('invoice_create',args=[a.pk]),{'discount':'99'})
        invoice=Invoice.objects.get();self.assertEqual(invoice.total,900)
        url=reverse('invoice_detail',args=[invoice.pk])
        payment={'amount':'400','method':'Cash','reference':'','token':str(uuid4())}
        self.assertEqual(self.client.post(url,payment).status_code,302)
        self.client.post(url,payment)
        self.assertEqual(Payment.objects.count(),1)
        self.assertEqual(invoice.balance,500)
        self.assertEqual(self.client.post(url,{**payment,'amount':'501','token':str(uuid4())}).status_code,200)
        self.assertEqual(Payment.objects.count(),1)
        self.client.post(url,{**payment,'amount':'500','token':str(uuid4())})
        self.assertEqual(invoice.balance,0)
        self.client.force_login(self.user)
        self.assertContains(self.client.get(url),'Paid in full')
        self.assertEqual(self.client.post(url,payment).status_code,403)
        self.client.force_login(User.objects.create_user('unrelated'))
        self.assertEqual(self.client.get(url).status_code,403)

    def test_customer_time_conflict_across_staff(self):
        self.book()
        another=Staff.objects.create(name='Another');another.services.add(self.service)
        self.assertEqual(self.client.post(reverse('booking'),{**self.data,'staff':another.pk}).status_code,200)
        self.assertEqual(Appointment.objects.count(),1)

    def test_database_enforces_unique_staff_reservations(self):
        from django.db import IntegrityError, transaction
        a=self.book()
        row=a.reservations.first()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Reservation.objects.create(appointment=a,staff=row.staff,date=row.date,minute=row.minute)

    def test_failed_reschedule_preserves_original_reservation(self):
        a=self.book()
        other=User.objects.create_user('busy_customer')
        self.client.force_login(other)
        self.client.post(reverse('booking'),{**self.data,'time':'13:00'})
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(reverse('reschedule',args=[a.pk]),{**self.data,'time':'13:00'}).status_code,200)
        a.refresh_from_db();self.assertEqual(a.time.hour,11)
        self.assertEqual(a.reservations.count(),60)
        self.assertTrue(a.reservations.filter(minute=660).exists())
