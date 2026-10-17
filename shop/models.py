from decimal import Decimal
from .validators import validate_video_size, validate_image_size
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator, FileExtensionValidator

class Translated(models.Model):
    name_az = models.CharField(max_length=160)
    name_ru = models.CharField(max_length=160)
    description_az = models.TextField(blank=True)
    description_ru = models.TextField(blank=True)
    class Meta: abstract = True
    def __str__(self): return self.name_az
    def localized(self, lang):
        self.title = self.name_ru if lang == 'ru' else self.name_az
        self.description = self.description_ru if lang == 'ru' else self.description_az
        return self

class Region(Translated):
    sample_art = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MaxValueValidator(2)])
    image = models.ImageField(upload_to='regions/', blank=True, validators=[validate_image_size])
    image_url = models.URLField(blank=True, help_text='Optional HTTPS image URL')
    @property
    def picture(self): return self.image.url if self.image else (self.image_url or ('/static/shop/regions.png' if self.sample_art is not None else ''))
    @property
    def art_style(self):
        return f'position:absolute;width:300%;max-width:none;height:100%;object-fit:fill;left:-{self.sample_art*100}%;top:0' if self.sample_art is not None and not self.image and not self.image_url else ''

class Category(Translated): pass

class Product(Translated):
    sample_art = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MaxValueValidator(7)])
    region = models.ForeignKey(Region, on_delete=models.PROTECT)
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    price = models.DecimalField(max_digits=9, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    discount = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(90)])
    image = models.ImageField(upload_to='products/', blank=True, validators=[validate_image_size])
    image_url = models.URLField(blank=True)
    unit_az = models.CharField(max_length=30, default='1 kq')
    unit_ru = models.CharField(max_length=30, default='1 кг')
    active = models.BooleanField(default=True)
    sample = models.BooleanField(default=False)
    @property
    def sale_price(self): return (self.price * (100-self.discount) / 100).quantize(Decimal('0.01'))
    @property
    def picture(self): return self.image.url if self.image else (self.image_url or ('/static/shop/products.png' if self.sample_art is not None else ''))
    @property
    def art_style(self):
        if self.sample_art is not None and not self.image and not self.image_url:
            return f'position:absolute;width:400%;max-width:none;height:200%;object-fit:fill;left:-{self.sample_art%4*100}%;top:-{self.sample_art//4*100}%'
        return ''

class Video(Translated):
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, blank=True, null=True)
    file = models.FileField(upload_to='videos/', validators=[FileExtensionValidator(['mp4','webm','mov']),validate_video_size])
    placement = models.CharField(max_length=20, choices=[('production','Production'),('packing','Order preparation')], default='production')
    reels = models.BooleanField(default=True)
    active = models.BooleanField(default=True)
    position = models.PositiveIntegerField(default=0)
    class Meta: ordering = ['position','id']

phone_validator = RegexValidator(r'^\+?[1-9]\d{7,14}$', 'Use international format, e.g. country code followed by the number.')
class StoreSettings(models.Model):
    name = models.CharField(max_length=100, default='FarmCart')
    logo = models.ImageField(upload_to='branding/', blank=True, validators=[validate_image_size])
    phone = models.CharField(max_length=16, blank=True, validators=[phone_validator])
    whatsapp = models.CharField(max_length=16, blank=True, validators=[phone_validator])
    email = models.EmailField(blank=True)
    address_az = models.TextField(blank=True)
    address_ru = models.TextField(blank=True)
    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
    def __str__(self): return 'Store configuration'
