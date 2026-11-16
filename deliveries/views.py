from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import role_required

from .forms import DeliveryForm, DeliveryItemFormSet, VoidDeliveryForm
from .models import AuditLog, Delivery, PriceRate


@login_required
def delivery_list(request):
    """BR-05/06 via Section 2.2: Recorder, Cashier, Manager can all view deliveries."""
    deliveries = Delivery.objects.select_related("fisher", "boat", "recorded_by").prefetch_related("items")

    fisher_q = request.GET.get("fisher", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()

    if fisher_q:
        deliveries = deliveries.filter(fisher__last_name__icontains=fisher_q) | deliveries.filter(
            fisher__first_name__icontains=fisher_q
        )
    if date_from:
        deliveries = deliveries.filter(landed_at__date__gte=date_from)
    if date_to:
        deliveries = deliveries.filter(landed_at__date__lte=date_to)

    return render(
        request,
        "deliveries/delivery_list.html",
        {
            "deliveries": deliveries.distinct(),
            "fisher_q": fisher_q,
            "date_from": date_from,
            "date_to": date_to,
        },
    )


@role_required("Recorder", "Manager")
def delivery_create(request):
    """BR-06: only a Recorder or a Manager may create deliveries."""
    if request.method == "POST":
        form = DeliveryForm(request.POST)
        formset = DeliveryItemFormSet(request.POST, instance=Delivery())
        if form.is_valid() and formset.is_valid():
            landed_at = form.cleaned_data["landed_at"]
            price_errors = []
            items_data = []
            for item_form in formset.forms:
                if not item_form.cleaned_data or item_form.cleaned_data.get("DELETE"):
                    continue
                species = item_form.cleaned_data["species"]
                grade = item_form.cleaned_data["grade"]
                rate = PriceRate.rate_for(species, grade, landed_at.date())
                if rate is None:  # BR-15
                    item_form.add_error(
                        None,
                        f"No price rate found for {species} grade {grade} on or before {landed_at.date()}.",
                    )
                    price_errors.append(True)
                else:
                    items_data.append((item_form, rate))

            if not price_errors:
                with transaction.atomic():
                    delivery = form.save(commit=False)
                    delivery.recorded_by = request.user
                    delivery.save()
                    for item_form, rate in items_data:
                        item = item_form.save(commit=False)
                        item.delivery = delivery
                        item.price_per_kg = rate.price_per_kg
                        item.save()
                    AuditLog.objects.create(
                        user=request.user,
                        table_name=AuditLog.Table.DELIVERY,
                        record_id=delivery.pk,
                        action=AuditLog.Action.CREATE,
                    )
                messages.success(request, f"Delivery {delivery.delivery_no} recorded.")
                return redirect("deliveries:delivery_detail", pk=delivery.pk)
    else:
        form = DeliveryForm()
        formset = DeliveryItemFormSet(instance=Delivery())

    return render(request, "deliveries/delivery_form.html", {"form": form, "formset": formset, "mode": "create"})


@login_required
def delivery_detail(request, pk):
    delivery = get_object_or_404(
        Delivery.objects.select_related("fisher", "boat", "recorded_by").prefetch_related("items__species"), pk=pk
    )
    can_edit = delivery.editable_by(request.user)
    can_void = request.user.is_manager and delivery.status != Delivery.Status.VOIDED
    return render(
        request,
        "deliveries/delivery_detail.html",
        {"delivery": delivery, "can_edit": can_edit, "can_void": can_void},
    )


@login_required
def delivery_edit(request, pk):
    delivery = get_object_or_404(Delivery, pk=pk)
    if not delivery.editable_by(request.user):  # BR-07
        raise PermissionDenied(
            "This delivery can no longer be edited. Recorders may only edit deliveries on the day they "
            "were recorded; later corrections require a Manager."
        )

    if request.method == "POST":
        form = DeliveryForm(request.POST, instance=delivery)
        formset = DeliveryItemFormSet(request.POST, instance=delivery)
        if form.is_valid() and formset.is_valid():
            landed_at = form.cleaned_data["landed_at"]
            price_errors = []
            items_data = []
            for item_form in formset.forms:
                if not item_form.cleaned_data or item_form.cleaned_data.get("DELETE"):
                    continue
                species = item_form.cleaned_data["species"]
                grade = item_form.cleaned_data["grade"]
                rate = PriceRate.rate_for(species, grade, landed_at.date())
                if rate is None:
                    item_form.add_error(
                        None,
                        f"No price rate found for {species} grade {grade} on or before {landed_at.date()}.",
                    )
                    price_errors.append(True)
                else:
                    items_data.append((item_form, rate))

            if not price_errors:
                with transaction.atomic():
                    delivery = form.save()
                    for item_form, rate in items_data:
                        item = item_form.save(commit=False)
                        item.delivery = delivery
                        item.price_per_kg = rate.price_per_kg
                        item.save()
                    formset.save_existing_objects()
                    for obj in formset.deleted_objects:
                        obj.delete()
                    AuditLog.objects.create(
                        user=request.user,
                        table_name=AuditLog.Table.DELIVERY,
                        record_id=delivery.pk,
                        action=AuditLog.Action.UPDATE,
                        reason="Edited via delivery edit form",
                    )
                messages.success(request, f"Delivery {delivery.delivery_no} updated.")
                return redirect("deliveries:delivery_detail", pk=delivery.pk)
    else:
        form = DeliveryForm(instance=delivery)
        formset = DeliveryItemFormSet(instance=delivery)

    return render(
        request,
        "deliveries/delivery_form.html",
        {"form": form, "formset": formset, "mode": "edit", "delivery": delivery},
    )


@role_required("Manager")
def delivery_void(request, pk):
    """BR-25: deliveries are never deleted, only voided, with a reason. Manager only."""
    delivery = get_object_or_404(Delivery, pk=pk)
    if delivery.status == Delivery.Status.VOIDED:
        messages.info(request, "This delivery is already voided.")
        return redirect("deliveries:delivery_detail", pk=delivery.pk)

    if request.method == "POST":
        form = VoidDeliveryForm(request.POST)
        if form.is_valid():
            reason = form.cleaned_data["reason"]
            with transaction.atomic():
                delivery.status = Delivery.Status.VOIDED
                delivery.void_reason = reason
                delivery.save()
                AuditLog.objects.create(
                    user=request.user,
                    table_name=AuditLog.Table.DELIVERY,
                    record_id=delivery.pk,
                    action=AuditLog.Action.VOID,
                    reason=reason,
                )
            messages.success(request, f"Delivery {delivery.delivery_no} voided.")
            return redirect("deliveries:delivery_detail", pk=delivery.pk)
    else:
        form = VoidDeliveryForm()

    return render(request, "deliveries/delivery_void.html", {"delivery": delivery, "form": form})
