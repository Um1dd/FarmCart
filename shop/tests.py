import tempfile
from decimal import Decimal
from io import BytesIO
from PIL import Image
from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import Product, Region, Category, StoreSettings, Video


class StoreTests(TestCase):
    def setUp(self):
        self.r = Region.objects.create(name_az="Naxçıvan", name_ru="Нахчыван")
        self.c = Category.objects.create(name_az="Bal", name_ru="Мёд")
        self.p = Product.objects.create(
            name_az="Dağ balı",
            name_ru="Горный мёд",
            region=self.r,
            category=self.c,
            price="20",
            discount=10,
        )
        self.s, _ = StoreSettings.objects.get_or_create(pk=1)
        self.s.whatsapp = ""
        self.s.save()

    def test_public_pages_and_language(self):
        for url in [
            "/",
            "/products/",
            f"/regions/{self.r.pk}/",
            f"/products/{self.p.pk}/",
            "/stories/",
            "/contact/",
            "/cart/",
            "/register/",
            "/login/",
        ]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.client.post("/language/", {"lang": "ru"})
        self.assertContains(self.client.get("/products/"), "Горный мёд")
        self.assertContains(self.client.get("/"), "У каждого региона свой вкус")

    def test_cart_discount_update_remove_and_checkout(self):
        self.client.post(f"/cart/{self.p.pk}/", {"quantity": "2"})
        response = self.client.get("/cart/")
        self.assertEqual(response.context["total"], Decimal("36"))
        self.assertEqual(response.context["whatsapp_link"], "")
        self.assertContains(response, "disabled")
        self.s.whatsapp = "+994501234567"
        self.s.save()
        self.assertIn(
            "https://wa.me/994501234567?text=",
            self.client.get("/cart/").context["whatsapp_link"],
        )
        self.client.post(f"/cart/{self.p.pk}/", {"action": "update", "quantity": 3})
        self.assertEqual(self.client.get("/cart/").context["total"], Decimal("54"))
        self.client.post(f"/cart/{self.p.pk}/", {"action": "remove"})
        self.assertEqual(self.client.get("/cart/").context["total"], 0)

    def test_invalid_quantity_inactive_and_redirect(self):
        self.client.post(
            f"/cart/{self.p.pk}/", {"quantity": "-20", "next": "//evil.test"}
        )
        self.assertEqual(self.client.session["cart"][str(self.p.pk)], 1)
        self.p.active = False
        self.p.save()
        self.assertEqual(self.client.post(f"/cart/{self.p.pk}/").status_code, 404)
        self.assertEqual(self.client.get("/cart/").context["total"], 0)

    def test_registration_login_profile_logout_and_authorization(self):
        response = self.client.post(
            "/register/",
            {
                "username": "customer",
                "password1": "BakuFarm!43825",
                "password2": "BakuFarm!43825",
            },
        )
        self.assertRedirects(response, "/account/")
        u = User.objects.get(username="customer")
        self.assertFalse(u.is_staff)
        self.assertTrue(u.check_password("BakuFarm!43825"))
        self.assertNotEqual(u.password, "BakuFarm!43825")
        self.client.post(
            "/account/",
            {"first_name": "Leyla", "last_name": "Ali", "email": "leyla@example.test"},
        )
        u.refresh_from_db()
        self.assertEqual(u.first_name, "Leyla")
        self.assertEqual(self.client.get("/admin/shop/product/").status_code, 302)
        self.client.post("/logout/")
        self.assertEqual(self.client.get("/account/").status_code, 302)
        self.assertRedirects(
            self.client.post(
                "/login/", {"username": "customer", "password": "BakuFarm!43825"}
            ),
            "/account/",
        )

    def test_csrf_and_mutation_methods(self):
        c = Client(enforce_csrf_checks=True)
        self.assertEqual(c.post(f"/cart/{self.p.pk}/").status_code, 403)
        self.assertEqual(c.post("/register/", {}).status_code, 403)
        self.assertEqual(self.client.get(f"/cart/{self.p.pk}/").status_code, 405)

    def test_admin_edit_and_media_upload(self):
        with (
            tempfile.TemporaryDirectory() as media,
            override_settings(MEDIA_ROOT=media),
        ):
            user = User.objects.create_superuser(
                "owner", "owner@example.test", "Owner!4568x"
            )
            from .models import OwnerState

            OwnerState.objects.filter(pk=1).update(
                owner=user, closed=True, verified_email="owner@gmail.com"
            )
            self.client.force_login(user)
            image = BytesIO()
            Image.new("RGB", (10, 10), "green").save(image, "PNG")
            response = self.client.post(
                f"/admin/shop/product/{self.p.pk}/change/",
                dict(
                    {
                        "variants-TOTAL_FORMS": "0",
                        "variants-INITIAL_FORMS": "0",
                        "variants-MIN_NUM_FORMS": "0",
                        "variants-MAX_NUM_FORMS": "1000",
                    },
                    name_az="Yeni bal",
                    name_ru="Новый мёд",
                    region=self.r.pk,
                    category=self.c.pk,
                    price="25.00",
                    discount="20",
                    unit_az="500 q",
                    unit_ru="500 г",
                    active="on",
                    image=SimpleUploadedFile(
                        "honey.png", image.getvalue(), content_type="image/png"
                    ),
                ),
            )
            self.assertEqual(response.status_code, 302)
            self.p.refresh_from_db()
            self.assertEqual(self.p.sale_price, Decimal("20"))
            self.assertTrue(self.p.image.storage.exists(self.p.image.name))
            self.assertContains(self.client.get("/products/"), "Yeni bal")
            video = SimpleUploadedFile(
                "production.webm", b"test-upload-storage", content_type="video/webm"
            )
            response = self.client.post(
                "/admin/shop/video/add/",
                dict(
                    name_az="Bal istehsalı",
                    name_ru="Производство мёда",
                    file=video,
                    product=self.p.pk,
                    placement="production",
                    reels="on",
                    active="on",
                    position=0,
                ),
            )
            self.assertEqual(response.status_code, 302)
            v = Video.objects.get()
            self.assertTrue(v.file.storage.exists(v.file.name))
            self.assertContains(self.client.get("/stories/"), v.file.url)
            self.assertContains(self.client.get(f"/products/{self.p.pk}/"), v.file.url)
            video_path = v.file.path
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    f"/admin/shop/video/{v.pk}/delete/", {"post": "yes"}
                )
            from pathlib import Path

            self.assertFalse(Path(video_path).exists())
            self.assertEqual(response.status_code, 302)
            self.assertFalse(Video.objects.exists())

    def test_seed_repeatability_and_filters(self):
        from django.core.management import call_command

        call_command("seed_demo")
        counts = (Product.objects.count(), Region.objects.count())
        call_command("seed_demo")
        self.assertEqual(counts, (Product.objects.count(), Region.objects.count()))
        self.assertContains(self.client.get("/products/?q=Dağ"), "Dağ balı")
        self.assertNotContains(self.client.get("/products/?q=nonexistent"), "Dağ balı")


class MediaTests(TestCase):
    def test_video_ranges_head_and_path_restrictions(self):
        from pathlib import Path

        with (
            tempfile.TemporaryDirectory() as media,
            override_settings(MEDIA_ROOT=media),
        ):
            Path(media, "clip.mp4").write_bytes(b"0123456789")
            response = self.client.get("/media/clip.mp4", HTTP_RANGE="bytes=2-5")
            self.assertEqual(response.status_code, 206)
            self.assertEqual(b"".join(response.streaming_content), b"2345")
            self.assertEqual(response["Content-Range"], "bytes 2-5/10")
            self.assertEqual(response["Content-Length"], "4")
            response = self.client.get("/media/clip.mp4", HTTP_RANGE="bytes=-3")
            self.assertEqual(b"".join(response.streaming_content), b"789")
            response = self.client.head("/media/clip.mp4")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Length"], "10")
            self.assertEqual(response.content, b"")
            self.assertEqual(
                self.client.get(
                    "/media/clip.mp4", HTTP_RANGE="bytes=12-14"
                ).status_code,
                416,
            )
            self.assertEqual(
                self.client.get(
                    "/media/clip.mp4", HTTP_RANGE="bytes=" + "9" * 5000 + "-"
                ).status_code,
                416,
            )
            Path(media, "unsafe.html").write_text("<script>alert(1)</script>")
            self.assertEqual(self.client.get("/media/unsafe.html").status_code, 404)
            self.assertEqual(self.client.get("/media/../.secret-key").status_code, 404)


class StoreUpdateTests(TestCase):
    def setUp(self):
        from .models import ProductVariant

        self.region = Region.objects.create(
            name_az="Test bölgə", name_ru="Тестовый регион"
        )
        self.category = Category.objects.create(name_az="Meyvə", name_ru="Фрукты")
        self.product = Product.objects.create(
            name_az="Test məhsul",
            name_ru="Тестовый товар",
            region=self.region,
            category=self.category,
            price="20",
            stock=5,
            discount=10,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, name_az="500 q", name_ru="500 г", price="12", stock=4
        )

    def test_variant_stock_price_and_delivery_whatsapp(self):
        from urllib.parse import urlsplit, parse_qs

        self.assertRedirects(
            self.client.post(f"/cart/{self.product.pk}/", {}),
            f"/products/{self.product.pk}/",
        )
        self.client.post(
            f"/cart/{self.product.pk}/", {"variant": self.variant.pk, "quantity": 99}
        )
        response = self.client.get("/cart/")
        self.assertEqual(response.context["rows"][0]["quantity"], 4)
        self.assertEqual(response.context["total"], Decimal("43.20"))
        self.client.post(
            "/cart/",
            {
                "customer_name": "Test Customer",
                "delivery_phone": "+994772506587",
                "delivery_address": "Test delivery address",
                "delivery_note": "Test note",
            },
        )
        response = self.client.get("/cart/")
        link = response.context["whatsapp_link"]
        self.assertTrue(link.startswith("https://wa.me/994772506587?"))
        text = parse_qs(urlsplit(link).query)["text"][0]
        for expected in ["500 q", "Test delivery address", "Test note", "43.20"]:
            self.assertIn(expected, text)
        self.client.post(
            f"/cart/{self.product.pk}/",
            {"variant": self.variant.pk, "action": "remove"},
        )
        self.assertEqual(self.client.get("/cart/").context["total"], 0)

    def test_stock_totals_across_variants_and_external_variant_rejected(self):
        from .models import ProductVariant

        second = ProductVariant.objects.create(
            product=self.product, name_az="1 kq", name_ru="1 кг", price="20", stock=5
        )
        self.client.post(
            f"/cart/{self.product.pk}/", {"variant": self.variant.pk, "quantity": 4}
        )
        self.client.post(
            f"/cart/{self.product.pk}/", {"variant": second.pk, "quantity": 4}
        )
        rows = self.client.get("/cart/").context["rows"]
        self.assertEqual(sum(row["quantity"] for row in rows), 5)
        self.product.stock = 2
        self.product.save()
        self.assertEqual(
            sum(row["quantity"] for row in self.client.get("/cart/").context["rows"]), 2
        )
        other = Product.objects.create(
            name_az="Other",
            name_ru="Other",
            region=self.region,
            category=self.category,
            price="1",
        )
        self.assertEqual(
            self.client.post(
                f"/cart/{other.pk}/", {"variant": self.variant.pk}
            ).status_code,
            404,
        )

    def test_contacts_localization_protected_region_delete(self):
        self.assertContains(self.client.get("/contact/"), "077 250 65 87")
        self.assertContains(
            self.client.get("/contact/"), "https://www.instagram.com/l.umidw/"
        )
        self.client.post("/language/", {"lang": "ru"})
        self.assertContains(self.client.get(f"/products/{self.product.pk}/"), "500 г")
        from django.db.models.deletion import ProtectedError

        with self.assertRaises(ProtectedError):
            self.region.delete()

    def test_admin_variant_crud_and_media_durability_validation(self):
        from .models import OwnerState

        user = User.objects.create_superuser("test_owner", "", "OwnerPass!537819")
        OwnerState.objects.filter(pk=1).update(
            owner=user, closed=True, verified_email="test_owner@gmail.com"
        )
        self.client.force_login(user)
        response = self.client.get(f"/admin/shop/product/{self.product.pk}/change/")
        self.assertContains(response, "variants-0-name_az")
        image = BytesIO()
        Image.new("RGB", (5, 5), "red").save(image, "PNG")
        with override_settings(MEDIA_DURABLE=False):
            response = self.client.post(
                "/admin/shop/region/add/",
                {
                    "name_az": "New",
                    "name_ru": "Новый",
                    "image": SimpleUploadedFile(
                        "region.png", image.getvalue(), content_type="image/png"
                    ),
                },
            )
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Qalıcı şəkil/video yaddaşı")
        self.assertFalse(Region.objects.filter(name_az="New").exists())

    def test_owner_content_crud_image_replace_clear_and_confirmation(self):
        from pathlib import Path
        from .models import OwnerState

        owner = User.objects.create_superuser("content_owner", "", "Owner!41298a")
        OwnerState.objects.filter(pk=1).update(
            owner=owner, closed=True, verified_email="content@gmail.com"
        )
        self.client.force_login(owner)
        with (
            tempfile.TemporaryDirectory() as media,
            override_settings(MEDIA_ROOT=media),
        ):

            def image(name, color):
                buffer = BytesIO()
                Image.new("RGB", (8, 8), color).save(buffer, "PNG")
                return SimpleUploadedFile(
                    name, buffer.getvalue(), content_type="image/png"
                )

            data = dict(
                name_az="CRUD product",
                name_ru="Товар",
                region=self.region.pk,
                category=self.category.pk,
                price="30",
                discount="10",
                stock="8",
                unit_az="1 kq",
                unit_ru="1 кг",
                active="on",
            )
            data.update(
                {
                    "variants-TOTAL_FORMS": "0",
                    "variants-INITIAL_FORMS": "0",
                    "variants-MIN_NUM_FORMS": "0",
                    "variants-MAX_NUM_FORMS": "1000",
                }
            )
            response = self.client.post(
                "/admin/shop/product/add/",
                {**data, "image": image("first.png", "green")},
            )
            self.assertEqual(response.status_code, 302)
            product = Product.objects.get(name_az="CRUD product")
            old = Path(product.image.path)
            self.assertTrue(old.exists())
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    f"/admin/shop/product/{product.pk}/change/",
                    {**data, "image": image("second.png", "blue")},
                )
            self.assertEqual(response.status_code, 302)
            product.refresh_from_db()
            self.assertFalse(old.exists())
            replacement = Path(product.image.path)
            self.assertTrue(replacement.exists())
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    f"/admin/shop/product/{product.pk}/change/",
                    {**data, "image-clear": "on", "discount": "0"},
                )
            self.assertEqual(response.status_code, 302)
            product.refresh_from_db()
            self.assertFalse(product.image)
            self.assertFalse(replacement.exists())
            self.assertEqual(product.sale_price, Decimal("30"))
            self.assertEqual(
                self.client.get(
                    f"/admin/shop/product/{product.pk}/delete/"
                ).status_code,
                200,
            )
            self.assertTrue(Product.objects.filter(pk=product.pk).exists())
            self.assertEqual(
                self.client.post(
                    f"/admin/shop/product/{product.pk}/delete/", {"post": "yes"}
                ).status_code,
                302,
            )
            self.assertFalse(Product.objects.filter(pk=product.pk).exists())
        for model, endpoint in [(Region, "region"), (Category, "category")]:
            self.assertEqual(
                self.client.post(
                    f"/admin/shop/{endpoint}/add/",
                    {"name_az": "CRUD item", "name_ru": "Тест"},
                ).status_code,
                302,
            )
            item = model.objects.get(name_az="CRUD item")
            self.assertEqual(
                self.client.post(
                    f"/admin/shop/{endpoint}/{item.pk}/change/",
                    {"name_az": "Edited item", "name_ru": "Тест"},
                ).status_code,
                302,
            )
            item.refresh_from_db()
            self.assertEqual(item.name_az, "Edited item")
            self.assertEqual(
                self.client.get(
                    f"/admin/shop/{endpoint}/{item.pk}/delete/"
                ).status_code,
                200,
            )
            self.assertEqual(
                self.client.post(
                    f"/admin/shop/{endpoint}/{item.pk}/delete/", {"post": "yes"}
                ).status_code,
                302,
            )
            self.assertFalse(model.objects.filter(pk=item.pk).exists())
        response = self.client.post(
            "/admin/shop/storesettings/1/change/",
            dict(
                name="Updated Store",
                phone="+994772506587",
                whatsapp="+994772506587",
                instagram_username="l.umidw",
                instagram_url="https://www.instagram.com/l.umidw/",
            ),
        )
        self.assertEqual(response.status_code, 302)
        self.assertContains(self.client.get("/contact/"), "Updated Store")
        self.assertEqual(
            self.client.get("/admin/shop/storesettings/1/delete/").status_code, 200
        )
        self.assertTrue(StoreSettings.objects.filter(pk=1).exists())
        self.assertEqual(
            self.client.post(
                "/admin/shop/storesettings/1/delete/", {"post": "yes"}
            ).status_code,
            302,
        )
        self.assertFalse(StoreSettings.objects.exists())
        for path in ["/", "/contact/", "/cart/"]:
            self.assertEqual(self.client.get(path).status_code, 200)
        response = self.client.post(
            "/admin/shop/storesettings/add/",
            {
                "name": "Restored Store",
                "phone": "+994772506587",
                "whatsapp": "+994772506587",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertContains(self.client.get("/contact/"), "Restored Store")


class CloudStorageRoutingTests(TestCase):
    @override_settings(
        CLOUDINARY_STORAGE={
            "CLOUD_NAME": "test-cloud",
            "API_KEY": "test-key",
            "API_SECRET": "test-secret",
            "SECURE": True,
        }
    )
    def test_signed_video_upload_url_extension_and_delete_use_video_resource(self):
        from unittest.mock import patch
        from .storage import CatalogCloudinaryStorage

        storage = CatalogCloudinaryStorage()
        with patch(
            "cloudinary.uploader.upload",
            return_value={"public_id": "media/videos/test_clip", "format": "mp4"},
        ) as upload:
            name = storage.save(
                "videos/clip.mp4", SimpleUploadedFile("clip.mp4", b"test")
            )
        self.assertEqual(name, "media/videos/test_clip.mp4")
        self.assertEqual(upload.call_args.kwargs["resource_type"], "video")
        self.assertIn("/video/upload/", storage.url(name))
        self.assertTrue(storage.url(name).startswith("https://"))
        from django.core.validators import FileExtensionValidator

        FileExtensionValidator(["mp4"])(SimpleUploadedFile(name, b"test"))
        with patch(
            "cloudinary.uploader.destroy", return_value={"result": "ok"}
        ) as destroy:
            self.assertTrue(storage.delete(name))
        self.assertEqual(destroy.call_args.args[0], "media/videos/test_clip")
        self.assertEqual(destroy.call_args.kwargs["resource_type"], "video")
        self.assertEqual(
            storage._get_resource_type("media/products/cheese.png"), "image"
        )


class VariantDashboardTests(TestCase):
    def test_authorized_variant_create_edit_delete_and_customer_denial(self):
        from .models import OwnerState, ProductVariant

        owner = User.objects.create_superuser("variant_owner", "", "VariantOwner!43729")
        OwnerState.objects.filter(pk=1).update(
            owner=owner, closed=True, verified_email="variant.owner@gmail.com"
        )
        region = Region.objects.create(name_az="Region", name_ru="Регион")
        category = Category.objects.create(name_az="Category", name_ru="Категория")
        product = Product.objects.create(
            name_az="Product",
            name_ru="Товар",
            region=region,
            category=category,
            price="20",
        )
        customer = User.objects.create_user(
            "variant_customer", password="Customer!28751"
        )
        self.client.force_login(customer)
        self.assertEqual(
            self.client.post("/admin/shop/productvariant/add/", {}).status_code, 302
        )
        self.client.force_login(owner)
        data = dict(
            product=product.pk,
            name_az="500 q",
            name_ru="500 г",
            price="12",
            stock=5,
            active="on",
        )
        self.assertEqual(
            self.client.post("/admin/shop/productvariant/add/", data).status_code, 302
        )
        variant = ProductVariant.objects.get(product=product)
        self.assertContains(self.client.get(f"/products/{product.pk}/"), "500 q")
        self.assertEqual(
            self.client.post(
                f"/admin/shop/productvariant/{variant.pk}/change/",
                {**data, "price": "15", "stock": 3},
            ).status_code,
            302,
        )
        variant.refresh_from_db()
        self.assertEqual(variant.price, Decimal("15"))
        self.assertEqual(variant.stock, 3)
        self.assertEqual(
            self.client.get(
                f"/admin/shop/productvariant/{variant.pk}/delete/"
            ).status_code,
            200,
        )
        self.assertTrue(ProductVariant.objects.filter(pk=variant.pk).exists())
        self.assertEqual(
            self.client.post(
                f"/admin/shop/productvariant/{variant.pk}/delete/", {"post": "yes"}
            ).status_code,
            302,
        )
        self.assertFalse(ProductVariant.objects.filter(pk=variant.pk).exists())
        self.assertTrue(Product.objects.filter(pk=product.pk).exists())
