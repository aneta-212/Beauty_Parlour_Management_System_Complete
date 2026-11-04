from django.core.management.base import BaseCommand
from salon.models import Service

class Command(BaseCommand):
    help = 'Add six sample services without changing existing services.'
    def handle(self, *args, **options):
        items = [
            ('Hair Styling', 'Haircuts and styling for your everyday look.', '799', 45, 'hair_styling.jpg'),
            ('Hair Spa', 'Deep conditioning and scalp care.', '999', 60, 'Hair_Spa.jpg'),
            ('Facial Treatment', 'A cleansing and refreshing facial treatment.', '1499', 60, 'Facial_Treatment.jpg'),
            ('Bridal Makeup', 'Makeup and hair styling for your wedding day.', '6999', 180, 'Bridal_Makeup.jpg'),
            ('Manicure', 'Hand care and nail treatment.', '699', 45, 'Manicure.jpg'),
            ('Pedicure', 'Foot care and nail treatment.', '799', 45, 'Pedicure.jpg'),
        ]
        added = 0
        for name, description, price, duration, image in items:
            _, created = Service.objects.get_or_create(name=name, defaults=dict(description=description, price=price, duration=duration, image='services/' + image))
            added += created
        self.stdout.write(self.style.SUCCESS(f'Added {added} sample services.'))
