from django.core.management.base import BaseCommand
from faker import Faker
import random
from customers.models import Client


class Command(BaseCommand):
    help = "Genera clientes de prueba (faker es_MX)"

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=50, help="Cantidad de clientes a crear")
        parser.add_argument("--clear", action="store_true", help="Marca como eliminados todos los existentes (soft delete)")

    def handle(self, *args, **opts):
        fake = Faker("es_MX")
        count = opts["count"]

        if opts["clear"]:
            for c in Client.objects.all():
                if hasattr(c, "soft_delete"):
                    c.soft_delete()
                else:
                    c.deleted = True
                    c.save(update_fields=["deleted"])
            self.stdout.write(self.style.WARNING("Todos los clientes existentes fueron marcados como eliminados."))

        REGIMENES = ["601", "603", "605", "606", "608", "612", "616", "OTRO"]
        USOS_CFDI = ["G01", "G03", "I01", "P01", "D01", "OTRO"]
        FORMAS_PAGO = ["EFECTIVO", "TRANSFERENCIA", "TARJETA", "CHEQUE", "PPD", "PUE", "OTRO"]

        created = 0
        for _ in range(count):
            nombre = fake.company()
            razon = fake.company().upper()
            rfc = fake.bothify(text="???######???").upper()

            client = Client(
                status=random.choice(["ALTA", "BAJA"]),
                nombre=nombre[:120],
                razon_social=razon[:200],
                rfc=rfc,
                regimen_fiscal=random.choice(REGIMENES),
                id_tributario=fake.bothify(text="TAX########"),

                calle=fake.street_name(),
                no_ext=str(fake.building_number()),
                colonia=fake.city_suffix(),
                colonia_sat=fake.secondary_address(),
                municipio=fake.city(),
                estado=fake.state(),
                pais="México",
                cp=fake.postcode(),
                telefono=fake.msisdn()[:10],
                poblacion=fake.city(),

                limite_credito=round(random.uniform(20000, 250000), 2),
                dias_credito=random.choice([0, 7, 15, 30, 45, 60, 90]),
                forma_pago=random.choice(FORMAS_PAGO),
                cuenta=str(fake.random_int(min=1000000, max=99999999)),
                uso_cfdi=random.choice(USOS_CFDI),
                observaciones=fake.sentence(nb_words=8),

                deleted=False,
            )
            client.save()
            created += 1

        self.stdout.write(self.style.SUCCESS(f"Se generaron {created} clientes de prueba correctamente."))
