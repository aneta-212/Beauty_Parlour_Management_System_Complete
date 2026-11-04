from django.contrib import admin
from .models import Service, Appointment, ContactMessage, Staff, StaffLeave, Invoice, Payment
from .forms import ServiceForm

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    form=ServiceForm
    list_display=['name','price','duration']
    search_fields=['name']

class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self,request): return False
    def has_change_permission(self,request,obj=None): return False
    def has_delete_permission(self,request,obj=None): return False

@admin.register(Appointment)
class AppointmentAdmin(ReadOnlyAdmin):
    list_display=['name','service','staff','date','time','status']
    list_filter=['status','date','staff']
    search_fields=['name','email','phone']

for model in [Staff,StaffLeave,Invoice,Payment]: admin.site.register(model,ReadOnlyAdmin)

@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display=['name','email','created_at']
    readonly_fields=['created_at']

from .models import Package,AppointmentItem,SalonSettings,ScheduleBlock,PaymentAdjustment,Notification,Review,Product,StockMovement,WaitlistEntry,AuditEvent
for model in [Package,AppointmentItem,SalonSettings,ScheduleBlock,PaymentAdjustment,Notification,Product,StockMovement,WaitlistEntry,AuditEvent]:
    admin.site.register(model,ReadOnlyAdmin)

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display=['appointment','rating','visible']
    list_editable=['visible']
    readonly_fields=['appointment','rating','comment','created_at']
    def has_add_permission(self,request):return False
