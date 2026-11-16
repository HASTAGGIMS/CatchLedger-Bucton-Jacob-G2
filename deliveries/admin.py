from django.contrib import admin

from .models import AuditLog, Boat, Delivery, DeliveryItem, Fisher, PriceRate, Species


@admin.register(Fisher)
class FisherAdmin(admin.ModelAdmin):
    list_display = ["member_no", "last_name", "first_name", "status", "date_joined"]
    search_fields = ["member_no", "last_name", "first_name"]
    list_filter = ["status"]


@admin.register(Boat)
class BoatAdmin(admin.ModelAdmin):
    list_display = ["registration_no", "boat_name", "owner", "boat_type", "status"]
    search_fields = ["registration_no", "boat_name"]
    list_filter = ["status", "boat_type"]


@admin.register(Species)
class SpeciesAdmin(admin.ModelAdmin):
    list_display = ["common_name", "local_name", "status"]
    search_fields = ["common_name", "local_name"]
    list_filter = ["status"]


@admin.register(PriceRate)
class PriceRateAdmin(admin.ModelAdmin):
    list_display = ["species", "grade", "price_per_kg", "effective_date", "set_by"]
    list_filter = ["grade", "species"]

    def save_model(self, request, obj, form, change):
        if not obj.set_by_id:
            obj.set_by = request.user
        super().save_model(request, obj, form, change)


class DeliveryItemInline(admin.TabularInline):
    model = DeliveryItem
    extra = 0
    readonly_fields = ["price_per_kg", "amount"]


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = ["delivery_no", "fisher", "boat", "landed_at", "status", "recorded_by"]
    list_filter = ["status"]
    search_fields = ["delivery_no"]
    inlines = [DeliveryItemInline]
    readonly_fields = ["delivery_no"]


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["logged_at", "user", "table_name", "record_id", "action"]
    list_filter = ["table_name", "action"]
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
