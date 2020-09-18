# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from django.db import models
from django.utils import timezone
from apps.router.models import Route
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext_lazy as _

__docformat__ = 'restructuredtext ru'


def prepare_route_data(route):
    """
    Подготавливает данные маршрута для отправки в подборщик.
    """
    # Отсеиваем маршруты, не предназначенные для ВПути.
    if not route.accept_carpool:
        return

    # Отсеиваем просроченные маршруты.
    if route.departure_time + timedelta(minutes=route.waiting_time_span) < timezone.now():
        return

    if len(route.places) < 2:
        return

    user_profile = {
        'id': route.user.id,
        'relations': {
            'following': [f.id for f in route.user.relationships.following()],
            'ignore': [b.id for b in route.user.relationships.blocking()],
            'communities': [group.id for group in route.user.userprofile.get_user_groups()]
        },
    }

    first_place = {
        'lat': route.places[0].latitude,
        'lon': route.places[0].longitude,
    }
    last_place = {
        'lat': route.places[-1].latitude,
        'lon': route.places[-1].longitude,
    }

    route_data = {
        'id': route.id,
        'role': route.role,
        'time': route.departure_time,
        'wait': route.waiting_time_span * 60,
        'seats': route.passengers_count or 1,
        'user_profile': user_profile,
        'places': [first_place, last_place]
    }
    return route_data


class MatchRequest(models.Model):
    """Запрос соответствия маршрутов."""
    route = models.OneToOneField(Route)
    request_id = models.IntegerField(blank=True, verbose_name=u'id запроса в подборщике')
    status_code = models.IntegerField(blank=True, null=True, verbose_name=u'статус')
    status_description = models.CharField(blank=True, null=True, max_length=255, verbose_name=u'описание статуса')



class Place(models.Model):
    """Deprecated. Will be deleted soon."""
    latitude = models.FloatField(verbose_name=u'широта точки встречи')
    longitude = models.FloatField(verbose_name=u'долгота точки встречи')
    address = models.CharField(blank=True, max_length=255, verbose_name=u'адрес точки встречи')
    time = models.DateTimeField(blank=True, default=datetime.fromtimestamp(0), null=True, verbose_name=u'время встречи')



MATCH_STATUS_CHOICES = (
    ('new', _(u'Новая')),
    ('accepted', _(u'Принята')),
    ('rejected', _(u'Отклонена')),
    ('done', _(u'Завершена')), # поездка успешно завершена
    )


MATCH_STATUS_WORKFLOW = {
    'new': ('new', 'accepted', 'rejected', 'done',),
    'accepted' : ('accepted', 'rejected', 'done',),
    'rejected' : ('rejected',),
    'done' : ('done',),
}


class Match(models.Model):
    """Deprecated. Will be deleted soon."""
    match_request = models.ForeignKey(MatchRequest, related_name='match_set')
    matched_request = models.ForeignKey(MatchRequest, related_name='matched_set')
    meeting = models.ForeignKey(Place, default=0, related_name='meeting_set', verbose_name=u'место посадки')
    dropoff = models.ForeignKey(Place, default=0, related_name='dropoff_set', verbose_name=u'место высадки')
    cost = models.DecimalField(blank=True, null=True, max_digits=7, decimal_places=2, verbose_name=u'стоимость')
    distance = models.IntegerField(verbose_name=u'длина маршрута, м')
    distance_extension = models.IntegerField(verbose_name=u'увеличение длины маршрута, м')
    status = models.CharField(_(u'статус подбора'), choices=MATCH_STATUS_CHOICES, max_length=9, default='new', blank=True)
    rating = models.IntegerField(_(u'оценка поездки'), default=0, blank=True)
    comment = models.CharField(_(u'комментарий'), max_length=255, default='', blank=True)


from signal_handlers import *
