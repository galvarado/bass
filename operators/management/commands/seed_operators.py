from django.core.management.base import BaseCommand
from django.utils import timezone
from faker import Faker
import random
from datetime import timedelta
from operators.models import Operator


class Command(BaseCommand):
    help = "Genera operadores de prueba (faker es_MX)"

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=50, help="Cantidad de operadores a crear")
        parser.add_argument("--clear", action="store_true", help="Marca como eliminados todos los existentes (soft delete)")

    def handle(self, *args, **opts):
        fake = Faker("es_MX")
        count = opts["count"]

        if opts["clear"]:
            for op in Operator.all_objects.all():
                op.delete()  # soft delete
            self.stdout.write(self.style.WARNING("Todos los operadores existentes fueron marcados como eliminados."))

        created = 0
        for _ in range(count):
            nombre = f"{fake.first_name()} {fake.last_name()} {fake.last_name()}"
            rfc = fake.bothify(text="???######???").upper()
            curp = fake.bothify(text="????######??????##").upper()

            op = Operator(
                status=random.choice(["ALTA", "BAJA"]),
                nombre=nombre,
                calle=fake.street_name(),
                no_ext=str(fake.building_number()),
                colonia=fake.city_suffix(),
                colonia_sat=fake.secondary_address(),
                municipio=fake.city(),
                estado=fake.state(),
                pais="MÉXICO",
                cp=fake.postcode(),
                telefono=fake.msisdn()[:10],
                rfc=rfc,
                curp=curp,
                tipo_sangre=random.choice(["A+", "O+", "B+", "AB+", "A-", "O-", "B-", "AB-"]),
                imss=str(fake.random_int(min=10000000000, max=99999999999)),
                fecha_nacimiento=fake.date_of_birth(minimum_age=25, maximum_age=60),
                fecha_ingreso=timezone.now().date() - timedelta(days=random.randint(30, 1500)),
                puesto=random.choice(["Operador", "Chofer A", "Chofer B", "Auxiliar de ruta"]),
                tipo_contrato=random.choice(["BASE", "TEMPORAL", "HONORARIOS"]),
                tipo_regimen=random.choice(["ASALARIADO", "INDEPENDIENTE"]),
                tipo_jornada=random.choice(["DIURNA", "NOCTURNA", "MIXTA"]),
                tipo_liquidacion=random.choice(["SEMANAL", "QUINCENAL", "MENSUAL"]),
                periodicidad=random.choice(["Semanal", "Quincenal", "Mensual"]),
                cuenta_bancaria=str(fake.random_int(min=10000000, max=99999999)),
                cuenta=str(fake.random_int(min=1000000, max=9999999)),
                poblacion=fake.city(),
                sueldo_fijo=round(random.uniform(400, 800), 2),
                comision=round(random.uniform(0, 10), 2),
                tope=round(random.uniform(5000, 15000), 2),

                # Documentos
                ine=fake.bothify(text="INE########"),
                ine_vencimiento=timezone.now().date() + timedelta(days=random.randint(180, 720)),
                licencia_federal=fake.bothify(text="LIC#######"),
                licencia_federal_vencimiento=timezone.now().date() + timedelta(days=random.randint(180, 720)),
                visa=fake.bothify(text="VISA#######"),
                visa_vencimiento=timezone.now().date() + timedelta(days=random.randint(180, 720)),
                pasaporte=fake.bothify(text="PASS#######"),
                pasaporte_vencimiento=timezone.now().date() + timedelta(days=random.randint(180, 720)),
                examen_medico=fake.bothify(text="EXM#######"),
                examen_medico_vencimiento=timezone.now().date() + timedelta(days=random.randint(180, 720)),
                rcontrol=fake.bothify(text="RCN#######"),
                rcontrol_vencimiento=timezone.now().date() + timedelta(days=random.randint(180, 720)),
                antidoping=fake.bothify(text="ANT#######"),
                antidoping_vencimiento=timezone.now().date() + timedelta(days=random.randint(180, 720)),

                deleted=False,
            )
            op.save()
            created += 1

        self.stdout.write(self.style.SUCCESS(f"Se generaron {created} operadores de prueba correctamente."))
