from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("health/", views.health, name="health"),
    path("accounts/register/", views.register, name="register"),
    path(
        "accounts/profile/",
        views.profile_settings,
        name="profile_settings",
    ),
    path("accounts/dashboard/", views.dashboard, name="dashboard"),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(template_name="core/login.html"),
        name="login",
    ),
    path(
        "accounts/logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),
    path("market/", views.market, name="market"),
    path("market/list/", views.add_product, name="add_product"),
    path("market/buy/<int:product_id>/", views.start_payment, name="start_payment"),
    path("work/", views.jobs, name="jobs"),
    path("work/post/", views.add_job, name="add_job"),
    path("work/apply/<int:job_id>/", views.submit_proposal, name="submit_proposal"),
    path(
        "work/<int:job_id>/proposals/<int:proposal_id>/accept/",
        views.accept_proposal,
        name="accept_proposal",
    ),
    path("payments/paymob/callback/", views.paymob_callback, name="paymob_callback"),
    path("faq/", views.faq, name="faq"),
]
