from django.core.management.base import BaseCommand
from shop.models import Region, Category, Product, StoreSettings
class Command(BaseCommand):
    help = 'Add clearly marked sample catalog entries without overwriting existing data.'
    def handle(self,*args,**kwargs):
        StoreSettings.objects.get_or_create(pk=1)
        regions=[]
        for index,(az,ru,da,dr,image) in enumerate([
            ('Naxçıvan','Нахчыван','Dağların qoynundan gələn saf dadlar','Чистый вкус горного края','region-nakhchivan.jpg'),
            ('Zaqatala','Загатала','Yaşıl meşələr, bərəkətli bağlar','Зелёные леса и щедрые сады','region-zaqatala.jpg'),
            ('Göyçay','Гёйчай','Nar bağlarının günəşli vətəni','Солнечная родина гранатовых садов','region-goychay.jpg')]):
            r,_=Region.objects.get_or_create(name_az=az,defaults=dict(name_ru=ru,description_az=da,description_ru=dr,sample_art=index))
            regions.append(r)
        categories=[]
        for az,ru in [('Bal və mürəbbə','Мёд и варенье'),('Çərəz və quru meyvə','Орехи и сухофрукты'),('Süd məhsulları','Молочные продукты'),('Meyvə və göyərti','Фрукты и зелень')]:
            c,_=Category.objects.get_or_create(name_az=az,defaults={'name_ru':ru});categories.append(c)
        data=[('Dağ çiçəyi balı','Горный цветочный мёд',0,0,'24.00','500 q','500 г','honey.jpg'),('Zaqatala fındığı','Загатальский фундук',1,1,'16.00','1 kq','1 кг','nuts.jpg'),('Təbii nar şirəsi','Натуральный гранатовый сок',2,3,'8.50','1 litr','1 л','pomegranate.jpg'),('Ənənəvi kənd pendiri','Традиционный деревенский сыр',0,2,'14.00','1 kq','1 кг','cheese.jpg'),('Qurudulmuş ərik','Сушёный абрикос',0,1,'18.00','500 q','500 г','apricots.jpg'),('Təzə qoz ləpəsi','Ядра грецкого ореха',1,1,'22.00','500 q','500 г','walnuts.jpg'),('Narşərab','Гранатовый соус наршараб',2,0,'12.00','250 ml','250 мл','sauce.jpg'),('Dağ kəklikotusu','Горный тимьян',0,3,'6.00','100 q','100 г','herbs.jpg')]
        for index,(az,ru,r,c,price,ua,ur,image) in enumerate(data):
            Product.objects.get_or_create(name_az=az,defaults=dict(name_ru=ru,region=regions[r],category=categories[c],price=price,unit_az=ua,unit_ru=ur,sample=True,sample_art=index,description_az='Nümunə məhsul. Bu məlumat və şəkil təqdimat üçündür. Satışdan əvvəl məhsulun mənşəyi, tərkibi və mövcudluğu mağaza sahibi tərəfindən yenilənməlidir.',description_ru='Демонстрационный товар. Информация и фото приведены для примера. Перед продажей владелец должен уточнить происхождение, состав и наличие.'))
        self.stdout.write(self.style.SUCCESS('Sample catalog available. Existing entries preserved. No sample videos or contact details invented.'))
