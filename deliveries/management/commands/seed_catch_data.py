from datetime import date, timedelta

from django.core.management.base import BaseCommand

from accounts.models import User
from deliveries.models import Boat, Fisher, PriceRate, Species


class Command(BaseCommand):
    help = "Seed sample fishers, boats, species and price rates so deliveries can be recorded and tested."

    def handle(self, *args, **options):
        manager = User.objects.filter(role=User.Role.MANAGER).first()
        if not manager:
            self.stdout.write(self.style.ERROR("No Manager account found. Run createsuperuser or seed_demo_users first."))
            return

        f1, _ = Fisher.objects.get_or_create(
            member_no="MBR-001",
            defaults={"last_name": "Dela Cruz", "first_name": "Ramon", "date_joined": date.today() - timedelta(days=200)},
        )
        f2, _ = Fisher.objects.get_or_create(
            member_no="MBR-002",
            defaults={"last_name": "Santos", "first_name": "Edgar", "date_joined": date.today() - timedelta(days=90)},
        )

        Boat.objects.get_or_create(
            registration_no="BT-0001",
            defaults={"owner": f1, "boat_name": "Pearl of the Sea", "boat_type": Boat.BoatType.MOTORIZED, "capacity_kg": 800},
        )
        Boat.objects.get_or_create(
            registration_no="BT-0002",
            defaults={"owner": f2, "boat_name": "Little Hope", "boat_type": Boat.BoatType.NON_MOTORIZED, "capacity_kg": 150},
        )

        tuna, _ = Species.objects.get_or_create(
            common_name="Yellowfin Tuna", defaults={"local_name": "Tambakol", "scientific_name": "Thunnus albacares"}
        )
        milkfish, _ = Species.objects.get_or_create(
            common_name="Milkfish", defaults={"local_name": "Bangus", "scientific_name": "Chanos chanos"}
        )

        for species in (tuna, milkfish):
            for grade, price in (("A", 220), ("B", 180), ("C", 140)):
                PriceRate.objects.get_or_create(
                    species=species,
                    grade=grade,
                    effective_date=date.today() - timedelta(days=30),
                    defaults={"price_per_kg": price, "set_by": manager},
                )

        self.stdout.write(self.style.SUCCESS("Sample fishers, boats, species and price rates are ready."))
