# FarmCart

Azerbaijani regional farm shop: Django 5.2, SQLite, server-rendered responsive frontend, and a protected Django administration dashboard. Azerbaijani is the default; Russian can be selected in the header. No Node build or external database is required for local development.

## Run locally

Windows: extract the project and double-click `START-WINDOWS.bat` (Python 3.12+ required). The launcher installs dependencies, migrates the database, adds samples only on first run, and opens the browser. Keep its terminal open. On macOS/Linux use `python3 scripts/run_local.py`. See `LOCAL-START.txt`.

Manual setup:

Requires Python 3.12+ with venv support.

```bash
./scripts/setup.sh
.venv/bin/python manage.py seed_demo     # optional, editable sample catalog
.venv/bin/python manage.py runserver 0.0.0.0:8001
```

Open the server in your local browser. `/admin/` is the owner dashboard. No administrator credentials are shipped. Initialize the owner only through the secret-gated, email-verified `/admin/setup/` workflow in [docs/OWNER_SETUP.md](docs/OWNER_SETUP.md). `createsuperuser` does not bypass this website’s verified-owner authorization. Customers register through `/register/` and receive no administrative privileges. `seed_demo` is repeatable and does not overwrite existing rows. Omit it for a blank catalog.

## Owner tasks

In `/admin/`:

- Manage bilingual regions, categories, products, units, prices, percentage discounts, availability, and sample labels. Region/category deletion is protected while products still use them; reassign or remove those products first.
- Upload product/region images (10 MB maximum). Uploaded images override optional image URLs and sample artwork. Image previews appear in edit forms. To replace sample content, edit it, upload the actual product image, clear the sample flag, and clear its sample art index if no real image is supplied.
- Add MP4, WebM, or MOV videos (100 MB maximum), with bilingual titles/descriptions, optional product association, placement (production or order preparation), Reels visibility, active state, and sort position. Videos appear on their product pages and selected homepage sections. Use browser-compatible H.264 MP4 or VP9 WebM; MOV compatibility depends on its codec. The admin edit form includes a playback preview. Customers have no upload route.
- View customers through the read-only Users directory. Roles cannot be changed there. Only the verified owner can create additional administrators using fresh password authentication and a single-use Gmail approval code.
- Open Store configuration to set the business name, logo, phone, WhatsApp, email, and bilingual address. Phone numbers use international format. The requested WhatsApp/phone and Instagram details are installed by migration; all remain editable. One configuration row is supported.
- Deletion uses Django's confirmation screen. Replaced/deleted local uploads are removed after the database transaction commits when no longer referenced.

## Customer workflow

The catalog, region pages, product details, and videos are public. Search matches both product languages; category filters work with regional browsing. Accounts support registration, login, logout, and profile changes. Public cart mutations require POST and CSRF protection. Carts use server-side sessions, persist across refreshes and application restarts, support 1–99 units per product, and calculate prices/discounts on the server using decimal arithmetic.

The cart displays a copyable order summary. With a configured WhatsApp number it opens `wa.me` with product names, quantities, unit prices, line totals, and total price. Without a number, the order button remains visible and disabled with an explanation. Reels “Order now” adds the associated product and opens the cart. There is no payment gateway or automatic order dispatch/history; the customer sends the prefilled WhatsApp message.

## Tests

```bash
.venv/bin/python manage.py test
.venv/bin/python manage.py check
.venv/bin/python manage.py collectstatic --noinput
```

Tests cover protected one-time owner setup, OTP expiry/attempt limits, fixed recipients, owner-approved additional administrators, recovery, concurrent initialization, customer/admin role restrictions, public pages, Russian translations, quantity/discount calculations, WhatsApp configuration, input bounds, inactive products, registration/profile/logout, customer/admin separation, CSRF, admin image/video uploads and edits, deletion, search, and seed repeatability. Browser validation during implementation also exercised desktop/mobile rendering, customer registration, language changes, cart actions, owner video upload, actual MP4 playback, Reels ordering, and confirmed deletion. Temporary browser test accounts and videos were removed.

## Data and architecture

- `shop/models.py`: translated region/category/product/video data and singleton store configuration.
- `shop/views.py`: storefront, session cart, accounts, language selection and WhatsApp composition.
- `shop/admin.py`: permission-protected content management and media previews.
- `shop/owner_security.py`, `shop/owner_views.py`, and `shop/admin_site.py`: verified ownership, setup, admin approvals, recovery, throttling and backend authorization.
- `shop/i18n.py`: Azerbaijani/Russian customer interface dictionary; product content is stored bilingually in the database.
- `shop/templates/shop/` and `shop/static/shop/`: responsive storefront, local font and artwork.
- `db.sqlite3`, `media/`, and `.secret-key` are persistent local state and ignored by Git. Preserve them across deployments and back them up securely together. Do not publish the database or media directory as unrestricted static site contents.

Sample product and landscape artwork is AI-generated illustration, not evidence of actual origin, production methods, or inventory. Each sample product is labeled, editable, and removable. No authentic footage was supplied, so production/packing/Reels sections show honest empty states until an administrator uploads videos. Manrope is bundled locally under the included SIL Open Font License; the storefront needs no external font/image service.

## Deployment configuration

This repository runs a development server by default. Before a public launch, use a production WSGI server with `config.wsgi:application`, an HTTPS reverse proxy, explicit `DJANGO_ALLOWED_HOSTS` (comma-separated hostnames), `DJANGO_DEBUG=0`, and a stable private `DJANGO_SECRET_KEY` from your deployment's secret storage. With debug disabled Django enforces HTTPS redirects and secure session/CSRF cookies. Set trusted proxy headers only for a proxy you control; set deployment-specific `DJANGO_CSRF_TRUSTED_ORIGINS` (comma-separated HTTPS origins) if serving separate origins. Run Django's deployment checks with production settings.

WhiteNoise serves collected static assets; configure Cloudinary for durable production uploads. The local catalog-media endpoint supports bounded video byte ranges and rejects non-catalog file types. Enforce request/upload limits at the proxy (image 10 MB / video 100 MB), disable execution in the upload directory, and retain `nosniff` headers. Scan untrusted files and transcode videos before broad public upload use. Authentication and verification limits are stored in the database and survive process restarts. Local SQLite is supported for development; owner setup on Render requires persistent PostgreSQL. No production administrator or external database/email/media credentials are shipped.

## Render deployment (free preview)

`render.yaml` uses Render's Free web service plan, without a paid disk or paid database. This is a preview configuration: SQLite data and uploaded media under `/tmp/farmcart` may disappear on restarts, redeployments, or instance replacement. Do not rely on it for real customer data or business inventory. Initial sample content is restored when the database is absent. The free instance may sleep when idle and take longer to open after inactivity.

1. Connect the GitHub repository using **New → Blueprint** in Render.
2. Confirm the service plan says **Free** and no paid disk/database is listed before deploying. If Render separately requires account/payment verification, that is an account requirement; this configuration does not bypass it. Do not select a paid upgrade to preview the app.
3. Render generates a private Django key, disables debug, collects static assets with WhiteNoise, and runs Gunicorn. Open the Render-provided URL after the service becomes Live.

For local use with durable data and no hosting plan, use the local launcher described above. A real store deployment needs durable database/media storage, backups, and administrator provisioning; those are not supplied by this free preview configuration. No default administrator password is shipped. Admin initialization is browser-based and does not need a Render shell. It is deliberately disabled on ephemeral Render SQLite; configure durable PostgreSQL and owner email delivery first as described in [docs/OWNER_SETUP.md](docs/OWNER_SETUP.md).

## Owner authentication and store updates

See [docs/OWNER_SETUP.md](docs/OWNER_SETUP.md) for secure Gmail/API configuration, first-owner registration, additional-admin approvals, recovery, persistent PostgreSQL/Cloudinary setup, content management, and end-to-end testing. The new flows never ship a default password and do not accept a browser-selected verification recipient. The free Render web-service plan is retained; external durable database, media, and mail credentials must be configured separately.
