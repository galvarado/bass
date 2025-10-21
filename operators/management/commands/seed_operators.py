from django.core.management.base import BaseCommand
from django.utils import timezone
from faker import Faker
import random
from datetime import timedelta
from operators.models import Operator

class Command(BaseCommand):
    help = "Genera operadores de prueba"

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=50, help="Cantidad a crear")
        parser.add_argument("--clear", action="store_true", help="Borra todos los existentes (soft)")

    def handle(self, *args, **opts):
        fake = Faker("es_MX")
        count = opts["count"]

        if opts["clear"]:
            Operator.objects.all().delete()  # elimina físicamente; quita si usas soft delete
            self.stdout.write(self.style.WARNING("Tabla operators vaciada."))

        created = 0
        for i in range(count):
            first = fake.first_name()
            paterno = fake.last_name()
            materno = fake.last_name()
            # RFC opcional (a veces vacío)
            rfc = fake.bothify(text="???######???").upper() if random.random() < 0.6 else None

            # Licencia única
            license_number = str(fake.random_int(min=100000, max=999999)) + str(i)

            # Vigencia 15–730 días al futuro
            expires = timezone.now().date() + timedelta(days=random.randint(15, 730))

            op = Operator(
                first_name=first,
                last_name_paterno=paterno,
                last_name_materno=materno,
                rfc=rfc,
                license_number=license_number,
                license_expires_at=expires,
                phone=fake.msisdn()[:10],
                email=fake.unique.email(),
                active=random.random() < 0.85,
                deleted=False,
            )
            op.save()
            created += 1

        self.stdout.write(self.style.SUCCESS(f"Creado(s) {created} operador(es)."))