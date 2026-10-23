import hashlib
import hmac
import json
import logging
import uuid
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .forms import (
    JobForm,
    ProductForm,
    ProfileSettingsForm,
    ProposalForm,
    RegistrationForm,
)
from .models import Job, Payment, Product, Profile, Proposal
from .paymob import PaymobError, create_checkout

logger = logging.getLogger(__name__)


def home(request):
    featured_products = Product.objects.filter(is_active=True)[:3]
    return render(
        request,
        "core/home.html",
        {"featured_products": featured_products},
    )


def health(request):
    return JsonResponse({"status": "ok"})


def faq(request):
    return render(request, "core/faq.html")


def jobs(request):
    listings = Job.objects.filter(is_open=True).select_related("client")
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    if query:
        listings = listings.filter(title__icontains=query)
    if category in Job.Category.values:
        listings = listings.filter(category=category)
    return render(
        request,
        "core/jobs.html",
        {
            "jobs": listings,
            "categories": Job.Category.choices,
            "selected_category": category,
            "query": query,
            "job_form": JobForm(),
            "proposal_form": ProposalForm(),
        },
    )


def register(request):
    if request.user.is_authenticated:
        return redirect("market")
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Welcome to KemetX. Your account is ready.")
        return redirect("market")
    return render(request, "core/register.html", {"form": form})


@login_required
def profile_settings(request):
    profile, _ = Profile.objects.get_or_create(
        user=request.user,
        defaults={"role": Profile.Role.FREELANCER},
    )
    form = ProfileSettingsForm(request.POST or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Your contact details have been updated.")
        return redirect("profile_settings")
    return render(request, "core/profile_settings.html", {"form": form})


@login_required
def dashboard(request):
    profile, _ = Profile.objects.get_or_create(
        user=request.user,
        defaults={"role": Profile.Role.FREELANCER},
    )
    if profile.role == Profile.Role.CLIENT:
        context = {
            "profile": profile,
            "my_jobs": Job.objects.filter(client=request.user).prefetch_related(
                "proposals__freelancer"
            ),
            "payments": Payment.objects.filter(buyer=request.user).select_related(
                "product"
            ),
        }
    elif profile.role == Profile.Role.MAKER:
        context = {
            "profile": profile,
            "my_products": Product.objects.filter(seller=request.user),
            "payments": Payment.objects.filter(buyer=request.user).select_related(
                "product"
            ),
        }
    else:
        context = {
            "profile": profile,
            "my_proposals": Proposal.objects.filter(
                freelancer=request.user
            ).select_related("job", "job__client"),
            "payments": Payment.objects.filter(buyer=request.user).select_related(
                "product"
            ),
        }
    return render(request, "core/dashboard.html", context)


def market(request):
    products = Product.objects.filter(is_active=True).select_related("seller")
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    if query:
        products = products.filter(title__icontains=query)
    if category in Product.Category.values:
        products = products.filter(category=category)
    form = ProductForm()
    return render(
        request,
        "core/market.html",
        {
            "products": products,
            "categories": Product.Category.choices,
            "selected_category": category,
            "query": query,
            "form": form,
        },
    )


@login_required
@require_POST
def add_product(request):
    profile, _ = Profile.objects.get_or_create(
        user=request.user,
        defaults={"role": Profile.Role.FREELANCER},
    )
    if profile.role != Profile.Role.MAKER and not request.user.is_staff:
        messages.error(request, "Only maker accounts can list marketplace products.")
        return redirect("market")
    form = ProductForm(request.POST)
    if not form.is_valid():
        errors = "; ".join(
            f"{field}: {', '.join(field_errors)}"
            for field, field_errors in form.errors.items()
        )
        messages.error(request, f"Please check the product details: {errors}")
        return redirect("market")
    product = form.save(commit=False)
    product.seller = request.user
    product.save()
    messages.success(request, "Your handmade product is now listed.")
    return redirect("market")


@login_required
@require_POST
def add_job(request):
    profile, _ = Profile.objects.get_or_create(
        user=request.user,
        defaults={"role": Profile.Role.FREELANCER},
    )
    if profile.role != Profile.Role.CLIENT and not request.user.is_staff:
        messages.error(request, "Only client accounts can post a freelance project.")
        return redirect("jobs")
    form = JobForm(request.POST)
    if not form.is_valid():
        errors = "; ".join(
            f"{field}: {', '.join(field_errors)}"
            for field, field_errors in form.errors.items()
        )
        messages.error(request, f"Please check the project details: {errors}")
        return redirect("jobs")
    job = form.save(commit=False)
    job.client = request.user
    job.save()
    messages.success(request, "Your project is now open to Egyptian freelancers.")
    return redirect("jobs")


@login_required
@require_POST
def submit_proposal(request, job_id):
    profile, _ = Profile.objects.get_or_create(
        user=request.user,
        defaults={"role": Profile.Role.FREELANCER},
    )
    if profile.role != Profile.Role.FREELANCER and not request.user.is_staff:
        messages.error(request, "Only freelancer accounts can submit proposals.")
        return redirect("jobs")
    form = ProposalForm(request.POST)
    if not form.is_valid():
        errors = "; ".join(
            f"{field}: {', '.join(field_errors)}"
            for field, field_errors in form.errors.items()
        )
        messages.error(request, f"Please check your proposal: {errors}")
        return redirect("jobs")
    proposal = form.save(commit=False)
    proposal.freelancer = request.user
    try:
        with transaction.atomic():
            job = Job.objects.select_for_update().filter(
                pk=job_id,
                is_open=True,
            ).first()
            if not job:
                messages.error(request, "This project is no longer open.")
                return redirect("jobs")
            if job.client_id == request.user.id:
                messages.error(
                    request,
                    "You cannot submit a proposal to your own project.",
                )
                return redirect("jobs")
            proposal.job = job
            proposal.save()
    except IntegrityError:
        if Proposal.objects.filter(job=job, freelancer=request.user).exists():
            messages.error(request, "You have already applied to this project.")
            return redirect("jobs")
        raise
    messages.success(request, "Your proposal has been sent to the client.")
    return redirect("jobs")


@login_required
@require_POST
def accept_proposal(request, job_id, proposal_id):
    with transaction.atomic():
        job = get_object_or_404(
            Job.objects.select_for_update(),
            pk=job_id,
            client=request.user,
            is_open=True,
        )
        proposal = get_object_or_404(Proposal, pk=proposal_id, job=job)
        job.is_open = False
        job.save(update_fields=["is_open"])
        job.proposals.exclude(pk=proposal.pk).update(
            status=Proposal.Status.DECLINED
        )
        proposal.status = Proposal.Status.ACCEPTED
        proposal.save(update_fields=["status"])
    messages.success(request, f"You selected {proposal.freelancer.username} for this project.")
    return redirect("dashboard")


@login_required
@require_POST
def start_payment(request, product_id):
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    if product.seller_id == request.user.id:
        messages.error(request, "You cannot purchase your own listing.")
        return redirect("market")
    profile = getattr(request.user, "profile", None)
    if not profile or not profile.phone:
        messages.error(
            request,
            "Add a valid Egyptian mobile number in your account settings before "
            "checking out.",
        )
        return redirect("profile_settings")

    amount_cents = int(
        (product.price_egp * Decimal("100")).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )
    payment = Payment.objects.create(
        buyer=request.user,
        product=product,
        merchant_order_id=uuid.uuid4(),
        amount_cents=amount_cents,
    )
    try:
        checkout_url, paymob_order_id = create_checkout(payment, request.user)
    except PaymobError as exc:
        payment.status = Payment.Status.FAILED
        payment.save(update_fields=["status"])
        messages.error(request, str(exc))
        return redirect("market")
    payment.paymob_order_id = paymob_order_id
    payment.save(update_fields=["paymob_order_id"])
    return redirect(checkout_url)


@csrf_exempt
@require_POST
def paymob_callback(request):
    if not settings.PAYMOB_HMAC_SECRET:
        logger.error("Paymob callback rejected because HMAC secret is not configured")
        return HttpResponse(status=503)
    supplied_hmac = request.GET.get("hmac", "")
    try:
        payload = json.loads(request.body)
        obj = payload["obj"]
        values = (
            obj["amount_cents"],
            obj["created_at"],
            obj["currency"],
            obj["error_occured"],
            obj["has_parent_transaction"],
            obj["id"],
            obj["integration_id"],
            obj["is_3d_secure"],
            obj["is_auth"],
            obj["is_capture"],
            obj["is_refunded"],
            obj["is_standalone_payment"],
            obj["is_voided"],
            obj["order"]["id"],
            obj["owner"],
            obj["pending"],
            obj["source_data"]["pan"],
            obj["source_data"]["sub_type"],
            obj["source_data"]["type"],
            obj["success"],
        )
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning("Malformed Paymob callback: %s", exc)
        return HttpResponse(status=400)

    message = "".join(str(value).lower() for value in values)
    expected_hmac = hmac.new(
        settings.PAYMOB_HMAC_SECRET.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha512,
    ).hexdigest()
    if not hmac.compare_digest(expected_hmac, supplied_hmac):
        logger.warning("Paymob callback HMAC verification failed")
        return HttpResponse(status=403)

    merchant_order_id = obj["order"].get("merchant_order_id")
    if not merchant_order_id:
        logger.warning("Verified Paymob callback had no merchant order ID")
        return HttpResponse(status=400)
    try:
        with transaction.atomic():
            payment = Payment.objects.select_for_update().get(
                merchant_order_id=merchant_order_id,
            )
            if payment.status != Payment.Status.PAID:
                is_valid_payment = (
                    obj["success"] is True
                    and obj["currency"] == "EGP"
                    and int(obj["amount_cents"]) == payment.amount_cents
                    and str(obj["integration_id"])
                    == str(settings.PAYMOB_INTEGRATION_ID)
                    and str(obj["order"]["id"]) == payment.paymob_order_id
                )
                payment.status = (
                    Payment.Status.PAID
                    if is_valid_payment
                    else Payment.Status.FAILED
                )
                payment.save(update_fields=["status"])
    except (Payment.DoesNotExist, ValueError, TypeError):
        logger.warning("Paymob callback did not match a valid KemetX payment")
        return HttpResponse(status=404)
    return HttpResponse(status=200)
