from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction


class Fisher(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "Active", "Active"
        INACTIVE = "Inactive", "Inactive"

    member_no = models.CharField(max_length=20, unique=True)
    last_name = models.CharField(max_length=50)
    first_name = models.CharField(max_length=50)
    contact_no = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=200, blank=True)
    date_joined = models.DateField(default=date.today)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        db_table = "fisher"
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.last_name}, {self.first_name} ({self.member_no})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class Boat(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "Active", "Active"
        INACTIVE = "Inactive", "Inactive"

    class BoatType(models.TextChoices):
        MOTORIZED = "Motorized", "Motorized"
        NON_MOTORIZED = "Non-motorized", "Non-motorized"

    owner = models.ForeignKey(Fisher, on_delete=models.PROTECT, related_name="boats")
    registration_no = models.CharField(max_length=30, unique=True)
    boat_name = models.CharField(max_length=50)
    boat_type = models.CharField(max_length=15, choices=BoatType.choices)
    capacity_kg = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        db_table = "boat"
        ordering = ["boat_name"]

    def __str__(self):
        return f"{self.boat_name} ({self.registration_no})"


class Species(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "Active", "Active"
        INACTIVE = "Inactive", "Inactive"

    common_name = models.CharField(max_length=60, unique=True)
    local_name = models.CharField(max_length=60, blank=True)
    scientific_name = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        db_table = "species"
        ordering = ["common_name"]
        verbose_name_plural = "species"

    def __str__(self):
        return self.common_name


class PriceRate(models.Model):
    class Grade(models.TextChoices):
        A = "A", "Grade A"
        B = "B", "Grade B"
        C = "C", "Grade C"

    species = models.ForeignKey(Species, on_delete=models.PROTECT, related_name="price_rates")
    grade = models.CharField(max_length=1, choices=Grade.choices)
    price_per_kg = models.DecimalField(max_digits=8, decimal_places=2)
    effective_date = models.DateField()
    set_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="price_rates_set")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "price_rate"
        ordering = ["-effective_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["species", "grade", "effective_date"], name="price_rate_species_grade_date_unique"
            )
        ]

    def __str__(self):
        return f"{self.species} grade {self.grade} @ {self.effective_date}"

    def clean(self):
        if self.price_per_kg is not None and self.price_per_kg <= 0:
            raise ValidationError({"price_per_kg": "Price per kg must be greater than 0."})

    @staticmethod
    def rate_for(species, grade, on_date):
        """BR-15: latest effective_date <= on_date for this species/grade."""
        return (
            PriceRate.objects.filter(species=species, grade=grade, effective_date__lte=on_date)
            .order_by("-effective_date")
            .first()
        )


def next_delivery_no():
    """BR-21: DLV-YYYYMMDD-NNN, unique, never reused."""
    today_str = date.today().strftime("%Y%m%d")
    prefix = f"DLV-{today_str}-"
    with transaction.atomic():
        last = (
            Delivery.objects.select_for_update()
            .filter(delivery_no__startswith=prefix)
            .order_by("-delivery_no")
            .first()
        )
        seq = int(last.delivery_no[-3:]) + 1 if last else 1
        return f"{prefix}{seq:03d}"


class Delivery(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "Active", "Active"
        VOIDED = "Voided", "Voided"

    delivery_no = models.CharField(max_length=20, unique=True, blank=True)
    fisher = models.ForeignKey(Fisher, on_delete=models.PROTECT, related_name="deliveries")
    boat = models.ForeignKey(Boat, on_delete=models.PROTECT, related_name="deliveries")
    landed_at = models.DateTimeField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    remarks = models.TextField(blank=True)
    void_reason = models.CharField(max_length=255, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="deliveries_recorded"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "delivery"
        ordering = ["-landed_at"]
        verbose_name_plural = "deliveries"

    def __str__(self):
        return self.delivery_no or f"Delivery #{self.pk}"

    def save(self, *args, **kwargs):
        if not self.delivery_no:
            self.delivery_no = next_delivery_no()
        super().save(*args, **kwargs)

    @property
    def total_weight_kg(self):
        return sum((item.weight_kg for item in self.items.all()), 0)

    @property
    def total_amount(self):
        return sum((item.amount for item in self.items.all()), 0)

    def editable_by(self, user):
        """BR-07: Recorder may edit only same calendar date it was recorded; Manager anytime."""
        if self.status == self.Status.VOIDED:
            return False
        if user.is_manager:
            return True
        if user.is_recorder:
            return self.created_at.date() == date.today()
        return False


class DeliveryItem(models.Model):
    class Grade(models.TextChoices):
        A = "A", "Grade A"
        B = "B", "Grade B"
        C = "C", "Grade C"

    delivery = models.ForeignKey(Delivery, on_delete=models.CASCADE, related_name="items")
    species = models.ForeignKey(Species, on_delete=models.PROTECT, related_name="delivery_items")
    grade = models.CharField(max_length=1, choices=Grade.choices)
    weight_kg = models.DecimalField(max_digits=8, decimal_places=2)
    price_per_kg = models.DecimalField(max_digits=8, decimal_places=2, editable=False)
    amount = models.DecimalField(max_digits=12, decimal_places=2, editable=False)

    class Meta:
        db_table = "delivery_item"
        constraints = [
            models.UniqueConstraint(fields=["delivery", "species", "grade"], name="delivery_item_species_grade_unique")
        ]

    def __str__(self):
        return f"{self.species} grade {self.grade} - {self.weight_kg}kg"

    def save(self, *args, **kwargs):
        self.amount = round(self.weight_kg * self.price_per_kg, 2)
        super().save(*args, **kwargs)


class AuditLog(models.Model):
    class Action(models.TextChoices):
        CREATE = "Create", "Create"
        UPDATE = "Update", "Update"
        VOID = "Void", "Void"
        DELETE = "Delete", "Delete"

    class Table(models.TextChoices):
        DELIVERY = "Delivery", "Delivery"
        DELIVERY_ITEM = "DeliveryItem", "DeliveryItem"
        PAYOUT = "Payout", "Payout"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="audit_entries")
    table_name = models.CharField(max_length=20, choices=Table.choices)
    record_id = models.IntegerField()
    action = models.CharField(max_length=10, choices=Action.choices)
    field_name = models.CharField(max_length=50, blank=True)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    reason = models.CharField(max_length=255, blank=True)
    logged_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "audit_log"
        ordering = ["-logged_at"]

    def __str__(self):
        return f"{self.action} on {self.table_name} #{self.record_id} by {self.user}"
