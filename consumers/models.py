# -*- coding: utf-8 -*-
from django.db import models

from libs.models import BaseModel
from apps.operations.models import Operation


CONSUMERS = (
    (u'vputi', u'ВПути'),
    (u'taxi', u'Такси'),
    (u'gooto', u'Gooto'),
    (u'sartaxi', u'SarTaxi'),
)

PLATFORMS = (
    (u'android', u'Android'),
    (u'ios', u'iOS'),
    (u'winphone', u'Windows Phone'),
    (u'vk', u'VK'),
    (u'web', u'Web'),
    (u'python', u'Python'),
)


class ConsumerVersions(BaseModel):
    consumer = models.CharField(max_length=50, choices=CONSUMERS)
    platform = models.CharField(max_length=50, choices=PLATFORMS)
    soft_major = models.IntegerField(default=0)
    soft_minor = models.IntegerField(default=1)
    soft_patch = models.IntegerField(default=0)
    hard_major = models.IntegerField(default=0)
    hard_minor = models.IntegerField(default=1)
    hard_patch = models.IntegerField(default=0)

    class Meta:
        verbose_name = 'Версии приложений'
        verbose_name_plural = 'Версии приложений'

    def __unicode__(self):
        return str(self.id)

    @classmethod
    def parse_version(cls, version):
        """
        Returns list of integers [<major>, <minor>, <patch>]
        """
        if not version:
            return None
        version = ''.join(c for c in version if c.isdigit() or c == '.').split('.')
        while len(version) < 3:
            version.append(0)
        for i in range(len(version)):
            version[i] = int(version[i])
        return version

    def check_version(self, version):
        """
        0 - обновление не требуется
        1 - обновление необязательно
        2 - обновление обазательно
        """
        v = self.parse_version(version)
        if not v:
            return None
        less_hard = v[0] < self.hard_major or v[1] < self.hard_minor or v[2] < self.hard_patch
        equal_hard = v[0] == self.hard_major and v[1] == self.hard_minor and v[2] == self.hard_patch
        less_soft = v[0] < self.soft_major or v[1] < self.soft_minor or v[2] < self.soft_patch
        equal_soft = v[0] == self.soft_major and v[1] == self.soft_minor and v[2] == self.soft_patch
        if less_hard or equal_hard:
            return 2
        elif less_soft or equal_soft:
            return 1
        else:
            return 0

    @classmethod
    def define_platform(cls, request):
        data = request.GET.get('consumer_platform') or request.META['HTTP_USER_AGENT']
        data = data.lower()
        for i in PLATFORMS:
            if i[0] in data:
                return i[0]
        return None

    @classmethod
    def define_consumer(cls, request):
        data = request.GET.get('consumer_name') or request.POST.get('consumer_name') or request.META['HTTP_USER_AGENT']
        data = data.lower()
        for i in CONSUMERS:
            if i[0] in data:
                return i[0]
        return 'gooto'

    @classmethod
    def define_obsolescence_level(cls, request):
        platform = cls.define_platform(request)
        consumer = cls.define_consumer(request)
        consumer_versions = cls.objects.safe_get(consumer=consumer, platform=platform)
        version = request.GET.get('consumer_version', '') or request.GET.get('app_version', '') or request.GET.get('appVersion', '')
        return consumer_versions.check_version(version) if consumer_versions else None


class ConsumerGeographicArea(BaseModel):
    consumer = models.CharField(max_length=50, choices=CONSUMERS)
    geographic_area = models.ForeignKey('router.GeographicArea', verbose_name=u'город')

    class Meta:
        verbose_name = u'Consumer\'s city'
        verbose_name_plural = u'Consumer\'s cities'

    def __unicode__(self):
        return 'ConsumerGeographicArea: %s' % self.id
