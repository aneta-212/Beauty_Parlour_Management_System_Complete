from django.db import migrations

def populate(apps,schema_editor):
    Appointment=apps.get_model('salon','Appointment')
    Item=apps.get_model('salon','AppointmentItem')
    Settings=apps.get_model('salon','SalonSettings')
    Settings.objects.get_or_create(pk=1)
    for a in Appointment.objects.select_related('service').all():
        if not Item.objects.filter(appointment=a).exists():
            Item.objects.create(appointment=a,service=a.service,name=a.service.name,price=a.quoted_price if a.quoted_price is not None else a.service.price,duration=a.duration_minutes or a.service.duration)

class Migration(migrations.Migration):
    dependencies=[('salon','0005_product_salonsettings_appointment_reminder_sent_at_and_more')]
    operations=[migrations.RunPython(populate,migrations.RunPython.noop)]
