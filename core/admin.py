from django.contrib import admin

from .models import Job, Payment, Product, Profile, Proposal


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "city")
    list_filter = ("role", "city")
    search_fields = ("user__username", "user__email")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("title", "seller", "category", "price_egp", "city", "is_active")
    list_filter = ("category", "city", "is_active")
    search_fields = ("title", "description", "seller__username")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("merchant_order_id", "buyer", "product", "amount_cents", "status")
    list_filter = ("status",)
    search_fields = ("merchant_order_id", "buyer__username", "product__title")
    readonly_fields = (
        "buyer",
        "product",
        "merchant_order_id",
        "amount_cents",
        "paymob_order_id",
        "created_at",
    )


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("title", "client", "category", "budget_egp", "is_open")
    list_filter = ("category", "is_open")
    search_fields = ("title", "description", "client__username")


@admin.register(Proposal)
class ProposalAdmin(admin.ModelAdmin):
    list_display = ("job", "freelancer", "bid_egp", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("job__title", "freelancer__username")
