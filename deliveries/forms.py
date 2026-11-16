from datetime import date

from django import forms
from django.forms import inlineformset_factory
from django.utils import timezone

from .models import Boat, Delivery, DeliveryItem, Fisher, PriceRate


class DeliveryForm(forms.ModelForm):
    class Meta:
        model = Delivery
        fields = ["fisher", "boat", "landed_at", "remarks"]
        widgets = {
            "landed_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "remarks": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fisher"].queryset = Fisher.objects.filter(status=Fisher.Status.ACTIVE)
        self.fields["boat"].queryset = Boat.objects.filter(status=Boat.Status.ACTIVE)
        self.fields["landed_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        for name, field in self.fields.items():
            field.widget.attrs.setdefault("class", "form-select" if name in ("fisher", "boat") else "form-control")

    def clean_landed_at(self):
        landed_at = self.cleaned_data["landed_at"]
        if landed_at > timezone.now():  # BR-18
            raise forms.ValidationError("The landing date and time cannot be in the future.")
        return landed_at

    def clean(self):
        cleaned = super().clean()
        fisher = cleaned.get("fisher")
        boat = cleaned.get("boat")
        if fisher and boat and boat.owner_id != fisher.id:
            # Not a hard rule in the SDD (any fisher may use any boat), informational only.
            pass
        return cleaned


class DeliveryItemForm(forms.ModelForm):
    class Meta:
        model = DeliveryItem
        fields = ["species", "grade", "weight_kg"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import Species

        self.fields["species"].queryset = Species.objects.filter(status=Species.Status.ACTIVE)
        for name, field in self.fields.items():
            field.widget.attrs.setdefault("class", "form-select" if name == "species" else "form-control")

    def clean_weight_kg(self):
        weight = self.cleaned_data["weight_kg"]
        if weight is None or weight <= 0 or weight > 5000:  # BR-19
            raise forms.ValidationError("Weight must be greater than 0 kg and not more than 5,000 kg.")
        return weight


class BaseDeliveryItemFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        landed_at = None
        if self.instance_form_has_landed_at():
            landed_at = self.data.get(f"{self.prefix}-__landed_at__")

        seen = set()
        valid_rows = 0
        for form in self.forms:
            if not hasattr(form, "cleaned_data") or form.cleaned_data.get("DELETE"):
                continue
            species = form.cleaned_data.get("species")
            grade = form.cleaned_data.get("grade")
            if not species or not grade:
                continue
            valid_rows += 1
            key = (species.id, grade)
            if key in seen:  # BR-20
                form.add_error(None, "A delivery cannot contain two items with the same species and grade.")
            seen.add(key)

        if valid_rows == 0:  # BR-17
            raise forms.ValidationError("A delivery must have at least one item.")

    def instance_form_has_landed_at(self):
        return False


DeliveryItemFormSet = inlineformset_factory(
    Delivery,
    DeliveryItem,
    form=DeliveryItemForm,
    formset=BaseDeliveryItemFormSet,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class VoidDeliveryForm(forms.Form):
    reason = forms.CharField(
        label="Reason for voiding",
        widget=forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
        min_length=5,
        help_text="At least 5 characters. This is recorded in the audit log.",
    )
