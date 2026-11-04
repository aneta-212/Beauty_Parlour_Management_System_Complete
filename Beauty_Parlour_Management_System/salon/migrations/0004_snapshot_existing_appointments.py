from django.db import migrations

def snapshot(apps,schema_editor):
    Appointment=apps.get_model('salon','Appointment')
    for a in Appointment.objects.select_related('service').all():
        changed=[]
        if not a.duration_minutes:
            a.duration_minutes=a.service.duration;changed.append('duration_minutes')
        if a.quoted_price is None:
            a.quoted_price=a.service.price;changed.append('quoted_price')
        if changed:a.save(update_fields=changed)

class Migration(migrations.Migration):
    dependencies=[('salon','0003_appointment_duration_minutes_and_more')]
    operations=[migrations.RunPython(snapshot,migrations.RunPython.noop)]
