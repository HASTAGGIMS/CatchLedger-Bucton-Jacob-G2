from datetime import date, timedelta

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from deliveries.models import Boat, Delivery, Fisher, PriceRate, Species


class DeliveryTestCase(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            username="mgr", email="mgr@test.com", password="pass12345", role=User.Role.MANAGER
        )
        self.recorder = User.objects.create_user(
            username="rec", email="rec@test.com", password="pass12345", role=User.Role.RECORDER
        )
        self.cashier = User.objects.create_user(
            username="csh", email="csh@test.com", password="pass12345", role=User.Role.CASHIER
        )
        self.fisher = Fisher.objects.create(member_no="MBR-100", last_name="Reyes", first_name="Ana")
        self.boat = Boat.objects.create(
            owner=self.fisher, registration_no="BT-100", boat_name="Test Boat", boat_type=Boat.BoatType.MOTORIZED
        )
        self.species = Species.objects.create(common_name="Test Tuna")
        PriceRate.objects.create(
            species=self.species,
            grade="A",
            price_per_kg=100,
            effective_date=date.today() - timedelta(days=10),
            set_by=self.manager,
        )

    def base_post_data(self, **overrides):
        data = {
            "fisher": self.fisher.id,
            "boat": self.boat.id,
            "landed_at": "2026-11-10T08:00",
            "remarks": "",
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "1",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-species": self.species.id,
            "items-0-grade": "A",
            "items-0-weight_kg": "10",
        }
        data.update(overrides)
        return data

    def test_recorder_can_create_delivery(self):
        self.client.login(username="rec", password="pass12345")
        response = self.client.post(reverse("deliveries:delivery_create"), self.base_post_data())
        self.assertEqual(response.status_code, 302)
        delivery = Delivery.objects.get()
        self.assertEqual(delivery.items.count(), 1)
        self.assertEqual(delivery.total_amount, 1000)  # 10kg * 100/kg

    def test_cashier_cannot_create_delivery(self):
        self.client.login(username="csh", password="pass12345")
        response = self.client.get(reverse("deliveries:delivery_create"))
        self.assertEqual(response.status_code, 403)

    def test_future_landing_date_rejected(self):
        self.client.login(username="rec", password="pass12345")
        future = (date.today() + timedelta(days=1)).strftime("%Y-%m-%dT08:00")
        response = self.client.post(reverse("deliveries:delivery_create"), self.base_post_data(landed_at=future))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Delivery.objects.count(), 0)

    def test_weight_over_limit_rejected(self):
        self.client.login(username="rec", password="pass12345")
        response = self.client.post(
            reverse("deliveries:delivery_create"), self.base_post_data(**{"items-0-weight_kg": "6000"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Delivery.objects.count(), 0)

    def test_missing_price_rate_rejected(self):
        no_rate_species = Species.objects.create(common_name="No Rate Fish")
        self.client.login(username="rec", password="pass12345")
        response = self.client.post(
            reverse("deliveries:delivery_create"), self.base_post_data(**{"items-0-species": no_rate_species.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Delivery.objects.count(), 0)

    def test_manager_can_void_delivery(self):
        self.client.login(username="rec", password="pass12345")
        self.client.post(reverse("deliveries:delivery_create"), self.base_post_data())
        delivery = Delivery.objects.get()

        self.client.login(username="mgr", password="pass12345")
        response = self.client.post(
            reverse("deliveries:delivery_void", args=[delivery.pk]), {"reason": "Wrong fisher recorded"}
        )
        self.assertEqual(response.status_code, 302)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, Delivery.Status.VOIDED)

    def test_recorder_cannot_edit_after_same_day(self):
        self.client.login(username="rec", password="pass12345")
        self.client.post(reverse("deliveries:delivery_create"), self.base_post_data())
        delivery = Delivery.objects.get()
        Delivery.objects.filter(pk=delivery.pk).update(created_at=date.today() - timedelta(days=2))
        delivery.refresh_from_db()

        response = self.client.get(reverse("deliveries:delivery_edit", args=[delivery.pk]))
        self.assertEqual(response.status_code, 403)

    def test_manager_can_edit_any_time(self):
        self.client.login(username="rec", password="pass12345")
        self.client.post(reverse("deliveries:delivery_create"), self.base_post_data())
        delivery = Delivery.objects.get()
        Delivery.objects.filter(pk=delivery.pk).update(created_at=date.today() - timedelta(days=30))

        self.client.login(username="mgr", password="pass12345")
        response = self.client.get(reverse("deliveries:delivery_edit", args=[delivery.pk]))
        self.assertEqual(response.status_code, 200)

    def test_all_roles_can_view_delivery_list(self):
        for username in ("rec", "csh", "mgr"):
            self.client.login(username=username, password="pass12345")
            response = self.client.get(reverse("deliveries:delivery_list"))
            self.assertEqual(response.status_code, 200)
