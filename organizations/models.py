# -*- coding: utf-8 -*-
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.models import User
from django.db import models
from django.contrib.gis.geos import GEOSGeometry


ORGANIZATION_TYPES = (
    ('taxi', _(u'Такси')),
    ('bus', _(u'Маршрутное такси')),
)


ORGANIZATION_STATUSES = (
    ('pending', u'Ожидает проверки'), # организация зарегистрирована, ожидается подтверждение регистрации по телефону
    ('accepted', u'Проверено'), # регистрация подтверждена, ожидается активация организации сотрудником ВПути
    ('active', u'Активно'), # организация активна и может выполнять свои функции
    ('suspended', u'Приостановлено'), # действие организации приостановлено по каким-то причинам
    ('canceled', u'Отменено'), # действие организации остановлено, через какое-то время она будет удалена для освобождения имени
)


class Organization(models.Model):
    """Организация."""
    owner = models.ForeignKey(User)
    name = models.CharField(_(u'название организации'), max_length=255, unique=True)
    type = models.CharField(_(u'тип организации'), choices=ORGANIZATION_TYPES, max_length=16)
    status = models.CharField(_(u'статус организации'), choices=ORGANIZATION_STATUSES, max_length=16)
    contact_phone = models.CharField(_(u'телефон организации'), max_length=14,
        help_text=u'этот телефон используется для подтверждени регистрации организации и не будет виден пользователям сервиса')
    rating = models.FloatField(_(u'рейтинг организации'), blank=True, default=0.0)
    members = models.ManyToManyField(User, verbose_name=_(u'члены организации'),  blank=True, related_name='organizations')
    date_modified = models.DateTimeField(_(u'дата изменения'), editable=False, auto_now=True)
    date_created = models.DateTimeField(_(u'дата создания'), editable=False, auto_now_add=True)
    geographic_polygon = models.TextField(u'геообласть')  # format: "POLYGON((<longitude> <latitude>,...))"

    def __unicode__(self):
        return self.name

    def save(self, *args, **kwargs):
        super(self.__class__, self).save(*args, **kwargs)
        self.members.add(self.owner)

    def is_polygon_contains_route(self, route):
        """
        Проверяет, попадает ли маршрут в географическую область организации.
        """
        if not route:
            return False
        start_point = GEOSGeometry('POINT(%s %s)' % (route.places[0].longitude, route.places[0].latitude), srid=4326)
        end_point = GEOSGeometry('POINT(%s %s)' % (route.places[-1].longitude, route.places[-1].latitude), srid=4326)
        polygon = GEOSGeometry(self.geographic_polygon, srid=4326)
        if polygon.contains(start_point) and polygon.contains(end_point):
            return True
        else:
            return False