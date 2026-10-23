import hashlib
import hmac
import json
import uuid
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Job, Payment, Product, Profile, Proposal

PAYMOB_HMAC_FIELDS = (
    "amount_cents",
    "created_at",
    "currency",
    "error_occured",
    "has_parent_transaction",
    "id",
    "integration_id",
    "is_3d_secure",
    "is_auth",
    "is_capture",
    "is_refunded",
    "is_standalone_payment",
    "is_voided",
    "order.id",
    "owner",
    "pending",
    "source_data.pan",
    "source_data.sub_type",
    "source_data.type",
    "success",
)


def paymob_callback_object(payment):
    return {
        "amount_cents": 12550,
        "created_at": "2026-10-23T00:00:00.000000",
        "currency": "EGP",
        "error_occured": False,
        "has_parent_transaction": False,
        "id": 12345,
        "integration_id": 456,
        "is_3d_secure": True,
        "is_auth": False,
        "is_capture": False,
        "is_refunded": False,
        "is_standalone_payment": True,
        "is_voided": False,
        "order": {
            "id": 789,
            "merchant_order_id": str(payment.merchant_order_id),
        },
        "owner": 111,
        "pending": False,
        "source_data": {"pan": "2346", "sub_type": "MasterCard", "type": "card"},
        "success": True,
    }


def paymob_callback_signature(callback_object, secret):
    values = []
    for field in PAYMOB_HMAC_FIELDS:
        value = callback_object
        for key in field.split("."):
            value = value[key]
        values.append(str(value).lower())
    return hmac.new(
        secret.encode(),
        "".join(values).encode(),
        hashlib.sha512,
    ).hexdigest()


class PublicPageTests(TestCase):
    def test_home_page_shows_egyptian_community(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Made for Egyptian talent")
        self.assertContains(response, "🇪🇬")

    def test_market_jobs_and_faq_pages_load(self):
        for page_name in ("market", "jobs", "faq"):
            with self.subTest(page=page_name):
                response = self.client.get(reverse(page_name))
                self.assertEqual(response.status_code, 200)

    def test_login_and_registration_pages_load(self):
        self.assertEqual(self.client.get(reverse("login")).status_code, 200)
        self.assertEqual(self.client.get(reverse("register")).status_code, 200)

    def test_health_endpoint_returns_ok(self):
        response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})


class AccountAndRoleTests(TestCase):
    def make_user(self, username, role):
        user = User.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="SafePassword!2026",
        )
        Profile.objects.create(user=user, role=role, phone="+201012345678")
        return user

    def test_registration_creates_profile_and_logs_user_in(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "noura",
                "email": "noura@example.com",
                "role": Profile.Role.MAKER,
                "city": "Aswan",
                "phone": "01012345678",
                "password1": "SafePassword!2026",
                "password2": "SafePassword!2026",
            },
        )

        self.assertRedirects(response, reverse("market"))
        profile = Profile.objects.get(user__username="noura")
        self.assertEqual(profile.role, Profile.Role.MAKER)
        self.assertEqual(profile.phone, "+201012345678")
        self.assertIn("_auth_user_id", self.client.session)

    def test_registration_rejects_non_egyptian_mobile_numbers(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "noura",
                "email": "noura@example.com",
                "role": Profile.Role.FREELANCER,
                "city": "Cairo",
                "phone": "12345",
                "password1": "SafePassword!2026",
                "password2": "SafePassword!2026",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "valid Egyptian mobile number")
        self.assertFalse(User.objects.filter(username="noura").exists())

    def test_only_makers_can_publish_market_products(self):
        client = self.make_user("client", Profile.Role.CLIENT)
        self.client.force_login(client)
        response = self.client.post(
            reverse("add_product"),
            {
                "title": "Woven basket",
                "description": "A handmade basket",
                "category": Product.Category.HOME,
                "price_egp": "250.00",
                "city": "Fayoum",
                "symbol": "✳",
            },
        )

        self.assertRedirects(response, reverse("market"))
        self.assertFalse(Product.objects.exists())

    def test_maker_can_publish_market_product(self):
        maker = self.make_user("maker", Profile.Role.MAKER)
        self.client.force_login(maker)
        response = self.client.post(
            reverse("add_product"),
            {
                "title": "Woven basket",
                "description": "A handmade basket",
                "category": Product.Category.HOME,
                "price_egp": "250.00",
                "city": "Fayoum",
                "symbol": "✳",
            },
        )

        self.assertRedirects(response, reverse("market"))
        self.assertEqual(Product.objects.get().seller, maker)

    def test_client_can_post_project_and_freelancer_can_propose(self):
        client = self.make_user("client", Profile.Role.CLIENT)
        freelancer = self.make_user("freelancer", Profile.Role.FREELANCER)
        self.client.force_login(client)
        response = self.client.post(
            reverse("add_job"),
            {
                "title": "Design a shop",
                "description": "Design a small online shop for a local brand.",
                "category": Job.Category.DESIGN,
                "budget_egp": "5000",
                "city": "Cairo",
            },
        )
        self.assertRedirects(response, reverse("jobs"))
        job = Job.objects.get()

        self.client.force_login(freelancer)
        response = self.client.post(
            reverse("submit_proposal", args=[job.pk]),
            {"cover_letter": "I can help with this project.", "bid_egp": "4500"},
        )

        self.assertRedirects(response, reverse("jobs"))
        proposal = Proposal.objects.get()
        self.assertEqual(proposal.job, job)
        self.assertEqual(proposal.freelancer, freelancer)

    def test_client_can_choose_proposal_and_close_project(self):
        client = self.make_user("client", Profile.Role.CLIENT)
        selected_freelancer = self.make_user("selected", Profile.Role.FREELANCER)
        other_freelancer = self.make_user("other", Profile.Role.FREELANCER)
        job = Job.objects.create(
            client=client,
            title="Build a portfolio",
            description="Create a portfolio for an Egyptian photographer.",
            category=Job.Category.DEVELOPMENT,
            budget_egp=Decimal("7000"),
        )
        selected = Proposal.objects.create(
            job=job,
            freelancer=selected_freelancer,
            cover_letter="I would love to help.",
            bid_egp=Decimal("6500"),
        )
        other = Proposal.objects.create(
            job=job,
            freelancer=other_freelancer,
            cover_letter="I can also help.",
            bid_egp=Decimal("6000"),
        )
        self.client.force_login(client)

        response = self.client.post(
            reverse("accept_proposal", args=[job.pk, selected.pk]),
        )

        self.assertRedirects(response, reverse("dashboard"))
        job.refresh_from_db()
        selected.refresh_from_db()
        other.refresh_from_db()
        self.assertFalse(job.is_open)
        self.assertEqual(selected.status, Proposal.Status.ACCEPTED)
        self.assertEqual(other.status, Proposal.Status.DECLINED)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)


class PaymobTests(TestCase):
    def setUp(self):
        self.buyer = User.objects.create_user(
            username="buyer",
            password="SafePassword!2026",
            email="buyer@example.com",
        )
        Profile.objects.create(
            user=self.buyer,
            role=Profile.Role.CLIENT,
            phone="+201012345678",
        )
        self.seller = User.objects.create_user(
            username="seller",
            password="SafePassword!2026",
            email="seller@example.com",
        )
        Profile.objects.create(
            user=self.seller,
            role=Profile.Role.MAKER,
            phone="+201112345678",
        )
        self.product = Product.objects.create(
            seller=self.seller,
            title="Handmade bowl",
            description="Clay bowl made in Egypt.",
            category=Product.Category.POTTERY,
            price_egp=Decimal("125.50"),
            city="Cairo",
        )

    @override_settings(
        PAYMOB_API_KEY="",
        PAYMOB_INTEGRATION_ID="",
        PAYMOB_IFRAME_ID="",
    )
    def test_checkout_fails_explicitly_when_paymob_is_not_configured(self):
        self.client.force_login(self.buyer)

        response = self.client.post(
            reverse("start_payment", args=[self.product.pk]),
        )

        self.assertRedirects(response, reverse("market"))
        payment = Payment.objects.get()
        self.assertEqual(payment.amount_cents, 12550)
        self.assertEqual(payment.status, Payment.Status.FAILED)

    @override_settings(
        PAYMOB_HMAC_SECRET="test-hmac-secret",
        PAYMOB_INTEGRATION_ID="456",
    )
    def test_valid_signed_paymob_callback_marks_order_paid(self):
        payment = Payment.objects.create(
            buyer=self.buyer,
            product=self.product,
            merchant_order_id=uuid.uuid4(),
            amount_cents=12550,
            paymob_order_id="789",
        )
        callback_object = paymob_callback_object(payment)
        signature = paymob_callback_signature(callback_object, "test-hmac-secret")

        response = self.client.post(
            f"{reverse('paymob_callback')}?hmac={signature}",
            data=json.dumps({"obj": callback_object}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PAID)
        self.client.force_login(self.buyer)
        dashboard_response = self.client.get(reverse("dashboard"))
        self.assertContains(dashboard_response, "EGP 125.50")

    @override_settings(PAYMOB_HMAC_SECRET="test-hmac-secret")
    def test_malformed_paymob_callback_is_rejected(self):
        response = self.client.post(
            f"{reverse('paymob_callback')}?hmac=invalid",
            data=json.dumps({"obj": {}}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    @override_settings(
        PAYMOB_HMAC_SECRET="test-hmac-secret",
        PAYMOB_INTEGRATION_ID="456",
    )
    def test_invalid_paymob_signature_is_rejected(self):
        payment = Payment.objects.create(
            buyer=self.buyer,
            product=self.product,
            merchant_order_id=uuid.uuid4(),
            amount_cents=12550,
            paymob_order_id="789",
        )
        callback_object = paymob_callback_object(payment)
        response = self.client.post(
            f"{reverse('paymob_callback')}?hmac=invalid",
            data=json.dumps({"obj": callback_object}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
