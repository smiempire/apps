# -*- coding: utf-8 -*-
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

from iospush.models import Device as IosPushDevice


class Device(models.Model):
    user = models.ForeignKey(User)
    last_activation = models.DateTimeField()
    is_active = models.BooleanField()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.is_active:
            self.last_activation = timezone.now()
        super(Device, self).save(*args, **kwargs)


class AndroidDevice(Device):
    token = models.TextField(unique=True)

    def __unicode__(self):
        return str(self.id)


class IosDevice(Device):
    device = models.ForeignKey(IosPushDevice)

    def __unicode__(self):
        return str(self.id)


class WindowsPhoneDevice(Device):
    uri = models.TextField(unique=True)

    def __unicode__(self):
        return str(self.id)


from signal_handlers import *
