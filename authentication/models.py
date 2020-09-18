# -*- coding: utf-8 -*-
from django.contrib.auth.models import User
from django.core.validators import validate_slug
from django.db import models
from django.utils.translation import ugettext_lazy as _
import settings

"""
class Consumer(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),   # rejected by service
        ('canceled', 'Canceled'),   # canceled by owner
    )
    owner = models.ForeignKey(User, related_name='clients')
    name = models.CharField(_('name'), max_length=255)
    description = models.TextField(_('description'), blank=True)
    status = models.CharField(_('status'), choices=STATUS_CHOICES, default='pending')
    key = models.SlugField(_('key'), max_length=settings.KEY_LENGTH, validators=[validate_slug])
    secret = models.CharField(_('secret'), max_length=settings.SECRET_LENGTH)
    redirect_uri = models.CharField(_('redirect URI'), max_length=255)

    created = models.DateTimeField(_('created'))

    class Meta:
        verbose_name = _('consumer')
        verbose_name_plural = _('consumers')

    def __unicode__(self):
        return u'%s' % self.name


class Nonce(models.Model):
    token_key = models.CharField(max_length=settings.KEY_LENGTH)
    consumer_key = models.CharField(max_length=settings.KEY_LENGTH)
    key = models.CharField(max_length=255)
"""

from signal_handlers import *
