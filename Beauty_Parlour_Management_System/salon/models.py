from django.db import models
from django.contrib.auth.models import User


class Service(models.Model):

    name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=8, decimal_places=2)
    duration = models.IntegerField()
    image = models.ImageField(upload_to='services/')

    def __str__(self):
        return self.name


class Appointment(models.Model):

    STATUS = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
        ('No-show', 'No-show'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='appointments')
    staff = models.ForeignKey('Staff', on_delete=models.PROTECT, null=True, blank=True)
    package = models.ForeignKey('Package', on_delete=models.SET_NULL, null=True, blank=True)
    walk_in = models.BooleanField(default=False)
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(default=0)
    quoted_price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=15)

    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT
    )

    date = models.DateField()
    time = models.TimeField()

    notes = models.TextField(
        blank=True,
        null=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS,
        default='Pending'
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    @property
    def treatment(self):
        return ', '.join(self.items.values_list('name', flat=True)) or self.service.name

    def __str__(self):
        return self.name

class ContactMessage(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=15, blank=True)
    message = models.TextField(max_length=5000)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Staff(models.Model):
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='beautician')
    name = models.CharField(max_length=100)
    services = models.ManyToManyField(Service, blank=True)
    active = models.BooleanField(default=True)
    start_time = models.TimeField(default='09:00')
    end_time = models.TimeField(default='20:00')
    weekdays = models.CharField(max_length=20, default='0,1,2,3,4,5,6', help_text='0=Monday through 6=Sunday')

    def __str__(self):
        return self.name


class StaffLeave(models.Model):
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE)
    date = models.DateField()
    reason = models.CharField(max_length=200, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['staff', 'date'], name='unique_staff_leave')]


class Reservation(models.Model):
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, related_name='reservations')
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE)
    date = models.DateField()
    minute = models.PositiveIntegerField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['staff', 'date', 'minute'], name='unique_staff_minute')]


class Invoice(models.Model):
    appointment = models.OneToOneField(Appointment, on_delete=models.PROTECT, related_name='invoice')
    service_name = models.TextField()
    subtotal = models.DecimalField(max_digits=8, decimal_places=2)
    discount = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def total(self):
        return self.subtotal - self.discount - self.credits

    @property
    def paid(self):
        from decimal import Decimal
        return sum((p.net for p in self.payments.all()), Decimal('0.00'))

    @property
    def credits(self):
        from decimal import Decimal
        return sum((a.amount for p in self.payments.all() for a in p.adjustments.all() if a.kind == 'Refund'), Decimal('0.00'))

    @property
    def balance(self):
        return self.total - self.paid


class Payment(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name='payments')
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    method = models.CharField(max_length=10, choices=[('Cash','Cash'),('UPI','UPI'),('Card','Card')])
    reference = models.CharField(max_length=100, blank=True)
    token = models.UUIDField(unique=True)
    recorded_by = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


    @property
    def net(self):
        from decimal import Decimal
        return self.amount - sum((a.amount for a in self.adjustments.all()), Decimal('0.00'))


class Package(models.Model):
    name = models.CharField(max_length=100)
    services = models.ManyToManyField(Service)
    discount = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    active = models.BooleanField(default=True)
    valid_until = models.DateField(null=True, blank=True)
    def __str__(self): return self.name


class AppointmentItem(models.Model):
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, related_name='items')
    service = models.ForeignKey(Service, on_delete=models.PROTECT)
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    duration = models.PositiveIntegerField()


class SalonSettings(models.Model):
    name = models.CharField(max_length=100, default='Beauty Parlour')
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=250, blank=True)
    weekday_open = models.TimeField(default='09:00')
    weekday_close = models.TimeField(default='20:00')
    sunday_open = models.TimeField(default='10:00')
    sunday_close = models.TimeField(default='18:00')
    change_notice_hours = models.PositiveIntegerField(default=0, help_text='Minimum hours before an appointment for customer cancellation/rescheduling')
    booking_horizon_days = models.PositiveIntegerField(default=90)

    @classmethod
    def current(cls):
        return cls.objects.filter(pk=1).first() or cls(pk=1)


class ScheduleBlock(models.Model):
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, null=True, blank=True, help_text='Leave empty to close the whole salon')
    date = models.DateField()
    start_time = models.TimeField(default='00:00')
    end_time = models.TimeField(default='23:59')
    reason = models.CharField(max_length=200)


class PaymentAdjustment(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name='adjustments')
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    kind = models.CharField(max_length=12, choices=[('Correction','Correction'),('Refund','Refund')])
    reason = models.CharField(max_length=300)
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    token = models.UUIDField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.CharField(max_length=500)
    link = models.CharField(max_length=200, default='/accounts/profile/')
    read = models.BooleanField(default=False)
    email_requested = models.BooleanField(default=True)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Review(models.Model):
    appointment = models.OneToOneField(Appointment, on_delete=models.CASCADE)
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(max_length=2000)
    visible = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Product(models.Model):
    name = models.CharField(max_length=100)
    unit = models.CharField(max_length=30, default='units')
    stock = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    low_stock = models.DecimalField(max_digits=10, decimal_places=2, default=5)
    active = models.BooleanField(default=True)
    def __str__(self): return self.name


class StockMovement(models.Model):
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.CharField(max_length=200)
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    token = models.UUIDField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)


class WaitlistEntry(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    service = models.ForeignKey(Service, on_delete=models.PROTECT)
    date = models.DateField()
    notes = models.CharField(max_length=300, blank=True)
    status = models.CharField(max_length=20, default='Waiting', choices=[('Waiting','Waiting'),('Offered','Offered'),('Booked','Booked'),('Closed','Closed')])
    created_at = models.DateTimeField(auto_now_add=True)


class AuditEvent(models.Model):
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=100)
    detail = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
