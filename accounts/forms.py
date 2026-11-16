from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, UserCreationForm
from django.core.files.storage import default_storage

from .models import User


class BootstrapFormMixin:
    """Adds Bootstrap 5 classes to every widget."""

    def _style_fields(self):
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs["class"] = "form-check-input"
            elif isinstance(widget, forms.Select):
                widget.attrs["class"] = "form-select"
            elif isinstance(widget, forms.ClearableFileInput):
                widget.attrs["class"] = "form-control"
            else:
                widget.attrs["class"] = "form-control"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class RegistrationForm(BootstrapFormMixin, UserCreationForm):
    # Managers are never self-registered; a Manager assigns that role later (BR-03).
    SELF_REGISTER_ROLES = [
        (User.Role.RECORDER, "Landing-site Recorder"),
        (User.Role.CASHIER, "Cooperative Cashier"),
    ]

    role = forms.ChoiceField(choices=SELF_REGISTER_ROLES, label="I am registering as")

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "contact_number", "role")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("first_name", "last_name", "email"):
            self.fields[name].required = True
        self.fields["username"].help_text = "Letters, digits and @/./+/-/_ only."
        self.fields["contact_number"].help_text = "Optional. Example: 0917 123 4567"
        self.fields["password1"].widget.attrs["autocomplete"] = "new-password"
        self.fields["password2"].widget.attrs["autocomplete"] = "new-password"
        self.fields["password2"].label = "Confirm password"
        self.fields["email"].error_messages["invalid"] = "Enter a valid email address (e.g., name@example.com)."

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_first_name(self):
        return self.cleaned_data["first_name"].strip()

    def clean_last_name(self):
        return self.cleaned_data["last_name"].strip()


class LoginForm(BootstrapFormMixin, AuthenticationForm):
    error_messages = {
        "invalid_login": "Invalid username or password. Please check your credentials and try again.",
        "inactive": "This account has been deactivated. Please contact the cooperative manager.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({"autofocus": True, "placeholder": "Username"})
        self.fields["password"].widget.attrs.update({"placeholder": "Password"})


class ProfileForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "contact_number", "profile_photo")
        widgets = {"profile_photo": forms.FileInput(attrs={"accept": "image/*"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("first_name", "last_name", "email"):
            self.fields[name].required = True
        self._old_photo = self.instance.profile_photo.name if self.instance.pk and self.instance.profile_photo else None

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Another account already uses this email.")
        return email

    def save(self, commit=True):
        user = super().save(commit)
        if commit and self._old_photo and "profile_photo" in self.changed_data and self._old_photo != user.profile_photo.name:
            default_storage.delete(self._old_photo)  # don't leave replaced photos behind
        return user


class StyledPasswordChangeForm(BootstrapFormMixin, PasswordChangeForm):
    pass


class ManagerUserForm(BootstrapFormMixin, forms.ModelForm):
    """Used by a Manager to change another user's role or active status."""

    class Meta:
        model = User
        fields = ("role", "is_active")
        labels = {"is_active": "Account is active (can log in)"}

    def __init__(self, *args, acting_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.acting_user = acting_user

    def clean(self):
        cleaned = super().clean()
        if self.acting_user and self.instance.pk == self.acting_user.pk:
            if cleaned.get("role") != User.Role.MANAGER or not cleaned.get("is_active"):
                raise forms.ValidationError(
                    "You cannot demote or deactivate your own account. Ask another Manager to do it."
                )
        return cleaned
