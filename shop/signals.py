from django.db.models.signals import post_delete, pre_save, post_save
from django.db import transaction
from .models import Product, Region, Video, StoreSettings

def remove_unused(sender, name, storage, field_name):
    if name and not sender.objects.filter(**{field_name:name}).exists(): storage.delete(name)
for model, field_name in [(Product,'image'),(Region,'image'),(Video,'file'),(StoreSettings,'logo')]:
    def cleanup(sender, instance, field_name=field_name, **kwargs):
        field=getattr(instance,field_name)
        if field.name: transaction.on_commit(lambda: remove_unused(sender,field.name,field.storage,field_name))
    def before_replace(sender, instance, field_name=field_name, **kwargs):
        previous=sender.objects.filter(pk=instance.pk).first() if instance.pk else None
        if previous:
            old=getattr(previous,field_name); new=getattr(instance,field_name)
            if old.name and old.name != new.name: instance._replaced_upload=(old.name,old.storage,field_name)
    def after_replace(sender, instance, **kwargs):
        if hasattr(instance,'_replaced_upload'):
            name,storage,field=instance._replaced_upload
            transaction.on_commit(lambda: remove_unused(sender,name,storage,field))
            del instance._replaced_upload
    post_delete.connect(cleanup,sender=model,weak=False)
    pre_save.connect(before_replace,sender=model,weak=False)
    post_save.connect(after_replace,sender=model,weak=False)
