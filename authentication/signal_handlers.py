# -*- coding: utf-8 -*-
from django.db.models.signals import pre_save
from apps.contacts.models import PhoneNumber


def deactivate_phone_numbers(sender, instance, **kwargs):
    """
    Деактивирует все предыдущие номера телефонов пользователя и дубликаты номера (независимо от пользователя).
    """
    if instance.is_active:
        pk = instance.pk
        # все предыдущие номера пользователя
        previous_phones = PhoneNumber.objects.filter(object_id=instance.object_id, is_active=True)
        # все дубликаты номера
        duplicate_phones = PhoneNumber.objects.filter(phone_number=instance.phone_number, is_active=True)
        # pk can be None if provided PhoneNumber doesn't saved yet.
        if pk:
            previous_phones = previous_phones.exclude(pk=pk)
            duplicate_phones = duplicate_phones.exclude(pk=pk)
        phones = list(previous_phones) + list(duplicate_phones)
        # call save() on each phone number to properly fire up all signals
        for p in phones:
            p.is_active = False
            p.save()


pre_save.connect(deactivate_phone_numbers, sender=PhoneNumber,
                 dispatch_uid='deactivate_phone_numbers')
