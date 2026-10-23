# KemetX

KemetX is an Egypt-focused independent-work community and handmade marketplace, built with Django. Clients can post freelance projects and choose from proposals, freelancers can apply and track their proposals, and makers can publish handmade products for sale in EGP.

## Included

- Egyptian-inspired landing page, FAQ, responsive layout, and Egypt flag in the footer
- Registration, login/logout, account settings, and client/freelancer/maker roles
- Remote-friendly project listings, client project posting, freelancer proposals, and proposal selection
- Handmade-products marketplace with maker listings and search/category filters
- Paymob Accept EGP checkout initiation and HMAC-verified server callback processing
- Django admin for account profiles, projects, proposals, products, and payments

## Local development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver
```

The app is served at <http://127.0.0.1:8000/>. Freelance projects are at `/work/`, handmade products at `/market/`, account registration at `/accounts/register/`, and the FAQ at `/faq/`.

Environment variables are read directly from the process; Django does not automatically load `.env`. Export its values with your local environment manager. Without Paymob settings, marketplace checkout reports that payment is unavailable; it will not simulate a successful payment.

## Paymob setup

Configure `PAYMOB_API_KEY`, `PAYMOB_INTEGRATION_ID`, `PAYMOB_IFRAME_ID`, and `PAYMOB_HMAC_SECRET` from your Paymob Accept merchant account. Register the absolute URL `https://<your-domain>/payments/paymob/callback/` as the Paymob transaction-response callback. The callback endpoint verifies Paymob's HMAC, EGP currency, amount, integration, and order before marking a payment paid. Keep these credentials private and use HTTPS in production.

Users add an Egyptian mobile number during registration; they can update their city and number in Account settings. This number is supplied as billing data for Paymob checkout.

The checkout integration does not implement escrow, refunds, maker payouts, marketplace commission, dispute handling, or delivery management. Configure and disclose commercial/payment terms before operating the marketplace with real customers. Paymob account credentials and a configured callback are required to validate a live payment end to end.

## Database and production

SQLite is used locally. To use PostgreSQL, set `DB_ENGINE=postgresql` and provide `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, and `DB_PORT`.

For production, set `DJANGO_DEBUG=False`, use a strong `DJANGO_SECRET_KEY`, and set `DJANGO_ALLOWED_HOSTS` to your hostnames. HTTPS redirects, secure session/CSRF cookies, and one-year HSTS are enabled when debug is disabled. If TLS terminates at a reverse proxy, configure it to overwrite `X-Forwarded-Proto` with the original request scheme. Set `DJANGO_SECURE_HSTS_SECONDS=0` only when intentionally disabling HSTS.

## Checks

```bash
python manage.py check
python manage.py test
```
