from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse


class Profile(models.Model):
    class Role(models.TextChoices):
        CLIENT = "client", "Client"
        FREELANCER = "freelancer", "Freelancer"
        MAKER = "maker", "Maker"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    city = models.CharField(max_length=80, blank=True)
    phone = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"


class Product(models.Model):
    class Category(models.TextChoices):
        TEXTILES = "textiles", "Textiles & embroidery"
        POTTERY = "pottery", "Pottery & ceramics"
        JEWELRY = "jewelry", "Jewelry"
        HOME = "home", "Home & decor"
        OTHER = "other", "Other handmade"

    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="products",
    )
    title = models.CharField(max_length=120)
    description = models.TextField(max_length=1200)
    category = models.CharField(max_length=20, choices=Category.choices)
    price_egp = models.DecimalField(
        max_digits=9,
        decimal_places=2,
        validators=[MinValueValidator(1)],
    )
    city = models.CharField(max_length=80)
    symbol = models.CharField(max_length=8, default="✳")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("market")


class Job(models.Model):
    class Category(models.TextChoices):
        DESIGN = "design", "Design & creative"
        DEVELOPMENT = "development", "Web & software"
        WRITING = "writing", "Writing & translation"
        MARKETING = "marketing", "Marketing"
        BUSINESS = "business", "Business support"

    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="posted_jobs",
    )
    title = models.CharField(max_length=140)
    description = models.TextField(max_length=3000)
    category = models.CharField(max_length=20, choices=Category.choices)
    budget_egp = models.DecimalField(
        max_digits=9,
        decimal_places=2,
        validators=[MinValueValidator(1)],
    )
    city = models.CharField(max_length=80, blank=True)
    is_open = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Proposal(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="proposals")
    freelancer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="proposals",
    )
    cover_letter = models.TextField(max_length=2000)
    bid_egp = models.DecimalField(
        max_digits=9,
        decimal_places=2,
        validators=[MinValueValidator(1)],
    )
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.SUBMITTED,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=("job", "freelancer"),
                name="one_proposal_per_freelancer_per_job",
            )
        ]

    def __str__(self):
        return f"{self.freelancer} → {self.job}"


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"

    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="market_payments",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="payments",
    )
    merchant_order_id = models.UUIDField(unique=True)
    amount_cents = models.PositiveIntegerField()
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
    )
    paymob_order_id = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.product} — {self.get_status_display()}"

    @property
    def amount_egp(self):
        return Decimal(self.amount_cents) / Decimal("100")
