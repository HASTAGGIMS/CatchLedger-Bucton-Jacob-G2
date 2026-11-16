from django.contrib.auth.models import AbstractUser, UserManager
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.functions import Lower
from django.urls import reverse


def validate_photo_size(image):
    max_mb = 2
    if image.size > max_mb * 1024 * 1024:
        raise ValidationError(f"Profile photo must be {max_mb} MB or smaller.")


contact_number_validator = RegexValidator(
    regex=r"^\+?[0-9][0-9\s\-]{6,18}$",
    message="Enter a valid contact number (digits, spaces or dashes; may start with +).",
)


class CatchLedgerUserManager(UserManager):
    """Superusers created from the command line are Managers."""

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", User.Role.MANAGER)
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    """Staff account of the cooperative (SDD entity: User / table app_user)."""

    class Role(models.TextChoices):
        RECORDER = "Recorder", "Recorder"
        CASHIER = "Cashier", "Cashier"
        MANAGER = "Manager", "Manager"

    email = models.EmailField("email address", unique=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.RECORDER)
    contact_number = models.CharField(max_length=20, blank=True, validators=[contact_number_validator])
    profile_photo = models.ImageField(
        upload_to="profile_photos/", blank=True, null=True, validators=[validate_photo_size]
    )

    objects = CatchLedgerUserManager()

    class Meta:
        db_table = "app_user"
        constraints = [
            models.UniqueConstraint(Lower("email"), name="app_user_email_ci_unique"),
            models.CheckConstraint(
                condition=models.Q(role__in=["Recorder", "Cashier", "Manager"]),
                name="app_user_role_valid",
            ),
        ]

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def display_name(self):
        return self.get_full_name() or self.username

    @property
    def is_recorder(self):
        return self.role == self.Role.RECORDER

    @property
    def is_cashier(self):
        return self.role == self.Role.CASHIER

    @property
    def is_manager(self):
        return self.role == self.Role.MANAGER

    def get_dashboard_url(self):
        return reverse(f"accounts:dashboard_{self.role.lower()}")

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)
