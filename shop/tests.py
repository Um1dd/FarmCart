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
        self.r=Region.objects.create(name_az='Naxçıvan',name_ru='Нахчыван')
        self.c=Category.objects.create(name_az='Bal',name_ru='Мёд')
        self.p=Product.objects.create(name_az='Dağ balı',name_ru='Горный мёд',region=self.r,category=self.c,price='20',discount=10)
        self.s=StoreSettings.objects.create()
    def test_public_pages_and_language(self):
        for url in ['/', '/products/', f'/regions/{self.r.pk}/',f'/products/{self.p.pk}/','/stories/','/contact/','/cart/','/register/','/login/']:
            self.assertEqual(self.client.get(url).status_code,200,url)
        self.client.post('/language/',{'lang':'ru'})
        self.assertContains(self.client.get('/products/'),'Горный мёд')
        self.assertContains(self.client.get('/'),'У каждого региона свой вкус')
    def test_cart_discount_update_remove_and_checkout(self):
        self.client.post(f'/cart/{self.p.pk}/',{'quantity':'2'})
        response=self.client.get('/cart/')
        self.assertEqual(response.context['total'],Decimal('36'))
        self.assertEqual(response.context['whatsapp_link'],'')
        self.assertContains(response,'disabled')
        self.s.whatsapp='+994501234567'; self.s.save()
        self.assertIn('https://wa.me/994501234567?text=',self.client.get('/cart/').context['whatsapp_link'])
        self.client.post(f'/cart/{self.p.pk}/',{'action':'update','quantity':3})
        self.assertEqual(self.client.get('/cart/').context['total'],Decimal('54'))
        self.client.post(f'/cart/{self.p.pk}/',{'action':'remove'})
        self.assertEqual(self.client.get('/cart/').context['total'],0)
    def test_invalid_quantity_inactive_and_redirect(self):
        self.client.post(f'/cart/{self.p.pk}/',{'quantity':'-20','next':'//evil.test'})
        self.assertEqual(self.client.session['cart'][str(self.p.pk)],1)
        self.p.active=False; self.p.save()
        self.assertEqual(self.client.post(f'/cart/{self.p.pk}/').status_code,404)
        self.assertEqual(self.client.get('/cart/').context['total'],0)
    def test_registration_login_profile_logout_and_authorization(self):
        response=self.client.post('/register/',{'username':'customer','password1':'BakuFarm!43825','password2':'BakuFarm!43825'})
        self.assertRedirects(response,'/account/')
        u=User.objects.get(username='customer'); self.assertFalse(u.is_staff); self.assertTrue(u.check_password('BakuFarm!43825'))
        self.assertNotEqual(u.password,'BakuFarm!43825')
        self.client.post('/account/',{'first_name':'Leyla','last_name':'Ali','email':'leyla@example.test'})
        u.refresh_from_db(); self.assertEqual(u.first_name,'Leyla')
        self.assertEqual(self.client.get('/admin/shop/product/').status_code,302)
        self.client.post('/logout/')
        self.assertEqual(self.client.get('/account/').status_code,302)
        self.assertRedirects(self.client.post('/login/',{'username':'customer','password':'BakuFarm!43825'}),'/account/')
    def test_csrf_and_mutation_methods(self):
        c=Client(enforce_csrf_checks=True)
        self.assertEqual(c.post(f'/cart/{self.p.pk}/').status_code,403)
        self.assertEqual(c.post('/register/',{}).status_code,403)
        self.assertEqual(self.client.get(f'/cart/{self.p.pk}/').status_code,405)
    def test_admin_edit_and_media_upload(self):
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            user=User.objects.create_superuser('owner','owner@example.test','Owner!4568x')
            self.client.force_login(user)
            image=BytesIO(); Image.new('RGB',(10,10),'green').save(image,'PNG')
            response=self.client.post(f'/admin/shop/product/{self.p.pk}/change/',dict(name_az='Yeni bal',name_ru='Новый мёд',region=self.r.pk,category=self.c.pk,price='25.00',discount='20',unit_az='500 q',unit_ru='500 г',active='on',image=SimpleUploadedFile('honey.png',image.getvalue(),content_type='image/png')))
            self.assertEqual(response.status_code,302)
            self.p.refresh_from_db(); self.assertEqual(self.p.sale_price,Decimal('20'))
            self.assertTrue(self.p.image.storage.exists(self.p.image.name))
            self.assertContains(self.client.get('/products/'),'Yeni bal')
            video=SimpleUploadedFile('production.webm',b'test-upload-storage',content_type='video/webm')
            response=self.client.post('/admin/shop/video/add/',dict(name_az='Bal istehsalı',name_ru='Производство мёда',file=video,product=self.p.pk,placement='production',reels='on',active='on',position=0))
            self.assertEqual(response.status_code,302)
            v=Video.objects.get(); self.assertTrue(v.file.storage.exists(v.file.name))
            self.assertContains(self.client.get('/stories/'),v.file.url)
            self.assertContains(self.client.get(f'/products/{self.p.pk}/'),v.file.url)
            video_path = v.file.path
            with self.captureOnCommitCallbacks(execute=True):
                response=self.client.post(f'/admin/shop/video/{v.pk}/delete/',{'post':'yes'})
            from pathlib import Path
            self.assertFalse(Path(video_path).exists())
            self.assertEqual(response.status_code,302); self.assertFalse(Video.objects.exists())
    def test_seed_repeatability_and_filters(self):
        from django.core.management import call_command
        call_command('seed_demo'); counts=(Product.objects.count(),Region.objects.count())
        call_command('seed_demo'); self.assertEqual(counts,(Product.objects.count(),Region.objects.count()))
        self.assertContains(self.client.get('/products/?q=Dağ'),'Dağ balı')
        self.assertNotContains(self.client.get('/products/?q=nonexistent'),'Dağ balı')

class MediaTests(TestCase):
    def test_video_ranges_head_and_path_restrictions(self):
        from pathlib import Path
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            Path(media, 'clip.mp4').write_bytes(b'0123456789')
            response = self.client.get('/media/clip.mp4', HTTP_RANGE='bytes=2-5')
            self.assertEqual(response.status_code, 206)
            self.assertEqual(b''.join(response.streaming_content), b'2345')
            self.assertEqual(response['Content-Range'], 'bytes 2-5/10')
            self.assertEqual(response['Content-Length'], '4')
            response = self.client.get('/media/clip.mp4', HTTP_RANGE='bytes=-3')
            self.assertEqual(b''.join(response.streaming_content), b'789')
            response = self.client.head('/media/clip.mp4')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Length'], '10')
            self.assertEqual(response.content, b'')
            self.assertEqual(self.client.get('/media/clip.mp4', HTTP_RANGE='bytes=12-14').status_code, 416)
            self.assertEqual(self.client.get('/media/clip.mp4', HTTP_RANGE='bytes='+'9'*5000+'-').status_code, 416)
            Path(media, 'unsafe.html').write_text('<script>alert(1)</script>')
            self.assertEqual(self.client.get('/media/unsafe.html').status_code, 404)
            self.assertEqual(self.client.get('/media/../.secret-key').status_code, 404)
