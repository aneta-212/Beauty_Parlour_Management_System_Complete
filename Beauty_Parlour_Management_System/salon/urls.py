from django.urls import path
from . import views

urlpatterns = [

    path('', views.home, name='home'),

    path('services/', views.services, name='services'),

    path('about/', views.about, name='about'),

    path('contact/', views.contact, name='contact'),

    path('gallery/', views.gallery, name='gallery'),

    path('booking/', views.booking, name='booking'),

    path('dashboard/', views.dashboard, name='dashboard'),

]
urlpatterns += [
    path('booking/slots/', views.available_slots, name='available_slots'),
    path('booking/<int:pk>/reschedule/', views.booking, name='reschedule'),
    path('booking/<int:pk>/cancel/', views.cancel_booking, name='cancel_booking'),
    path('dashboard/appointments/<int:pk>/status/', views.appointment_status, name='appointment_status'),
    path('dashboard/staff/', views.staff_list, name='staff_list'),
    path('dashboard/staff/add/', views.staff_edit, name='staff_add'),
    path('dashboard/staff/<int:pk>/', views.staff_edit, name='staff_edit'),
    path('dashboard/leave/add/', views.leave_add, name='leave_add'),
    path('dashboard/leave/<int:pk>/delete/', views.leave_delete, name='leave_delete'),
    path('dashboard/services/', views.service_list, name='service_list'),
    path('dashboard/services/add/', views.service_manage, name='service_add'),
    path('dashboard/services/<int:pk>/', views.service_manage, name='service_edit'),
    path('dashboard/inbox/', views.inbox, name='inbox'),
    path('dashboard/appointments/<int:pk>/bill/', views.invoice_create, name='invoice_create'),
    path('invoices/<int:pk>/', views.invoice_detail, name='invoice_detail'),
]

from . import extra_views as more
urlpatterns += [
    path('notifications/',more.notifications,name='notifications'),
    path('waitlist/',more.waitlist,name='waitlist'),
    path('waitlist/<int:pk>/action/',more.waitlist_action,name='waitlist_action'),
    path('reviews/',more.reviews,name='reviews'),
    path('appointments/<int:pk>/review/',more.review,name='review'),
    path('packages/',more.packages,name='packages'),
    path('dashboard/packages/add/',more.package_edit,name='package_add'),
    path('dashboard/packages/<int:pk>/',more.package_edit,name='package_edit'),
    path('dashboard/inventory/',more.inventory,name='inventory'),
    path('dashboard/products/add/',more.product_edit,name='product_add'),
    path('dashboard/products/<int:pk>/',more.product_edit,name='product_edit'),
    path('dashboard/products/<int:pk>/stock/',more.stock_change,name='stock_change'),
    path('dashboard/payments/<int:pk>/adjust/',more.payment_adjust,name='payment_adjust'),
    path('dashboard/blocks/',more.blocks,name='blocks'),
    path('dashboard/blocks/add/',more.block_add,name='block_add'),
    path('dashboard/blocks/<int:pk>/delete/',more.block_delete,name='block_delete'),
    path('dashboard/settings/',more.salon_settings,name='salon_settings'),
    path('dashboard/staff/<int:pk>/account/',more.staff_account,name='staff_account'),
    path('dashboard/calendar/',more.calendar,name='calendar'),
    path('dashboard/walk-in/',more.walk_in,name='walk_in'),
    path('dashboard/appointments/<int:pk>/edit/',more.walk_in,name='manage_booking'),
    path('dashboard/customers/',more.customers,name='customers'),
    path('dashboard/customers/<int:pk>/',more.customer_detail,name='customer_detail'),
    path('dashboard/activity/',more.activity,name='activity'),
    path('dashboard/reports/',more.reports,name='reports'),
    path('dashboard/backups/',more.backups,name='backups'),
    path('dashboard/waitlist/',more.waitlist_manage,name='waitlist_manage'),
]
