# -*- coding: utf-8 -*-
from django.db.models.signals import post_save

from apps.devices.models import AndroidDevice, IosDevice, WindowsPhoneDevice


def deactivate_previous_android_devices(sender, instance, **kwargs):
    # если активируется одно из android-устройств, то деактивируем все остальные устройства пользователя
    if instance.is_active:
        AndroidDevice.objects.filter(user=instance.user).exclude(id=instance.id).update(is_active=False)
        IosDevice.objects.filter(user=instance.user).update(is_active=False)
        WindowsPhoneDevice.objects.filter(user=instance.user).update(is_active=False)
post_save.connect(deactivate_previous_android_devices, sender=AndroidDevice,
                  dispatch_uid='deactivate_previous_android_devices')


def deactivate_previous_ios_devices(sender, instance, **kwargs):
    # если активируется одно из ios-устройств, то деактивируем все остальные устройства пользователя
    if instance.is_active:
        IosDevice.objects.filter(user=instance.user).exclude(id=instance.id).update(is_active=False)
        AndroidDevice.objects.filter(user=instance.user).update(is_active=False)
        WindowsPhoneDevice.objects.filter(user=instance.user).update(is_active=False)
post_save.connect(deactivate_previous_ios_devices, sender=IosDevice,
                  dispatch_uid='deactivate_previous_ios_devices')


def deactivate_previous_windows_phone_devices(sender, instance, **kwargs):
    # если активируется одно из windows phone-устройств, то деактивируем все остальные устройства пользователя
    if instance.is_active:
        WindowsPhoneDevice.objects.filter(user=instance.user).exclude(id=instance.id).update(is_active=False)
        IosDevice.objects.filter(user=instance.user).update(is_active=False)
        AndroidDevice.objects.filter(user=instance.user).update(is_active=False)
post_save.connect(deactivate_previous_windows_phone_devices, sender=WindowsPhoneDevice,
                  dispatch_uid='deactivate_previous_windows_phone_devices')
