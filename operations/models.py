# -*- coding: utf-8 -*-
from datetime import timedelta
import json
import uuid
from django.contrib.auth.models import User
from django.db import models
from django.db.models import Manager
from django.utils import timezone
import settings
from apps.contacts.settings import PHONE_VERIFIER_DISPATCH_COUNT


OPERATION_CLIENTS = (
    ('android', u'Android'),
    ('ios', u'iOS'),
    ('vk', u'VK'),
    ('web', u'Web'),
    ('python', u'Python'),
)


class OperationManager(Manager):
    def collect_expired(self):
        """
        Mark outdated operations as expired without firing signals.
        :returns Number of collected requests.
        """
        return Operation.objects.filter(date_expires__lte=timezone.now(), status='new').update(status='expired')


class Operation(models.Model):
    """
    Запрос на выполнение операции.
    """
    NEW = 'new'
    DONE = 'done'
    EXPIRED = 'expired'
    STATUS_CHOICES = (
        (NEW, u'Новый'),
        (DONE, u'Выполнен'),
        (EXPIRED, u'Просрочен'),
    )
    operation_key = models.SlugField(u'имя операции')
    uid = models.SlugField(u'ключь запроса')
    user = models.ForeignKey(User, blank=True, null=True, related_name='operations')
    _data = models.TextField(u'связанные данные в формате json', default='{}', db_column='data')
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='new')
    date_expires = models.DateTimeField(u'срок годности')
    date_created = models.DateTimeField(u'дата создания')
    date_modified = models.DateTimeField(u'дата изменения')
    key = models.CharField(max_length=50, null=True)
    client = models.CharField(max_length=30, choices=OPERATION_CLIENTS, blank=True, null=True)

    objects = OperationManager()

    class Meta:
        verbose_name = u'запрос операции'
        verbose_name_plural = u'запросы операций'
        unique_together = ('operation_key', 'uid')

    def __unicode__(self):
        return u'%s with uid %s in %s' % (self.operation_key, self.uid, self.status)

    def save(self, *args, **kwargs):
        if not self.uid:
            self.uid = str(uuid.uuid4())
            # paranoid check for uniqueness of operation_key and uid fields
            while Operation.objects.filter(operation_key=self.operation_key, uid=self.uid).exists():
                self.uid = str(uuid.uuid4())

        if hasattr(self, '_cached_data'):
            self._data = json.dumps(self._cached_data)

        t = timezone.now()
        if not self.date_expires:
            self.date_expires = t + timedelta(milliseconds=settings.OPERATION_EXPIRATION_PERIOD)
        self.date_modified = t
        if not self.date_created:
            self.date_created = self.date_modified
        super(Operation, self).save(*args, **kwargs)

    def get_data(self):
        if not hasattr(self, '_cached_data'):
            self._cached_data = json.loads(self._data)
        return self._cached_data

    def set_data(self, val):
        self._cached_data = val

    data = property(get_data, set_data)

    @classmethod
    def define_client(cls, data):
        data = data.lower()
        if 'android' in data:
            return 'android'
        elif 'ios' in data:
            return 'ios'
        elif 'vk' in data:
            return 'vk'
        elif 'web' in data:
            return 'web'
        elif 'python' in data:
            return 'python'
        else:
            return None

    def _is_whatsapp_received(self):
        """
        Возвращает статус доставки последнего WhatsApp-сообщения, ассоциированного с данной операцией.
        """
        msg = self.whatsappmessage_set.all().order_by('-date_created')[:1]
        return True if msg and msg[0].is_received else False
    is_whatsapp_received = property(_is_whatsapp_received)