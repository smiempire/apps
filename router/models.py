# -*- coding: utf-8 -*-

import math
import urllib2
import random
import string
from datetime import timedelta, datetime

from libs.config import BaseEnumerate
import requests
from django.contrib.auth.models import User
from django.db import models, router, DatabaseError, transaction
from django.db.models import signals, AutoField, Q
from django.utils import timezone
from django.utils.dateformat import format
from django.utils.translation import ugettext_lazy as _
from django.contrib.gis.geos import GEOSGeometry
from django.conf import settings
from recurrence.fields import RecurrenceField
from recurrence.base import serialize
from transliterate import translit

from transmission.settings import DEFAULT_ROUTE_COST, DEFAULT_ROUTE_DISTANCE, OVER_ROUTE_DISTANCE_PRICE, CARPOOL_COEFFICIENT
from apps.organizations.models import Organization
from apps.consumers.models import CONSUMERS
from libs.utils import string_to_hashtag, int_or_none, to_float_or_none
from libs.twitter_api import create_tweet
from libs.models import BaseManager, BaseDatedModel, BaseModel
from api_v1.models import Param


class PushType(BaseEnumerate):
    """
    Push type
    """

    SYSTEM_INFO = 0

    # For driver
    FOUND_ANOTHER_DRIVER = 1
    PASSENGER_CHOSEN_YOU = 2
    PASSENGER_CANCELED_ORDER = 3
    NEW_ROUTE = 4
    DEFERRED_ROUTES = 5
    PASSENGER_DELETED_ROUTE = 6

    # For passenger
    CAR_IS_WAITING_FOR_YOU = 101
    FOUND_NEW_DRIVER = 102
    TRIP_VOTE = 103
    FIVE_FREE_MINUTES_OF_WAITING = 104
    DRIVER_CANCELED_ORDER = 105

    values = {
        SYSTEM_INFO: u'Системная информация',
        # For driver
        FOUND_ANOTHER_DRIVER:  u'Пассажир выбрал другого водителя',
        PASSENGER_CHOSEN_YOU: u'Пассажир выбрал вас',
        PASSENGER_CANCELED_ORDER: u'Пассажир отменил заказ',
        NEW_ROUTE: u'Новая заявка',
        DEFERRED_ROUTES: u'Напоминание об отложенной поездке',
        PASSENGER_DELETED_ROUTE: u'Пассажир удалил заказ',
        # For passenger
        CAR_IS_WAITING_FOR_YOU: u'Вас ожидает ',
        FOUND_NEW_DRIVER: u'Найден новый водитель ',
        TRIP_VOTE: u'Пожалуйста, оцените свою поездку!',
        FIVE_FREE_MINUTES_OF_WAITING: u'У вас осталось 5 минут бесплатного ожидания',
        DRIVER_CANCELED_ORDER: u'Водитель отказался от вашего заказа'
    }


ROLE_CHOICES = (
    ('driver', _(u'Водитель')),
    ('passenger', _(u'Пассажир')),
)


class Recurrence(models.Model):
    dtstart = models.DateTimeField(null=True, blank=True)
    dtend = models.DateTimeField(null=True, blank=True)
    recurrence = RecurrenceField()


class GeographicArea(models.Model):
    """
    Географическая область.
    """
    name = models.CharField(u'название', max_length=255)
    key = models.CharField(u'символьный идентификатор', max_length=255, unique=True)
    geographic_polygon = models.TextField(u'полигон')  # format: "POLYGON((<longitude> <latitude>,...))"
    area = models.FloatField(u'площадь', blank=True)

    class Meta:
        verbose_name = u'Географическая область'
        verbose_name_plural = u'Географические области'

    def __unicode__(self):
        return self.name

    def save(self, force_insert=False, force_update=False, using=None):
        """
        Вычисляет площадь полигона при сохранении области.
        """
        self.area = GEOSGeometry(self.geographic_polygon, srid=4326).area
        super(GeographicArea, self).save(force_insert, force_update, using)

    @classmethod
    def define_geographic_area(cls, lat, lon):
        if not lat or not lon:
            return None
        point = GEOSGeometry('POINT(%s %s)' % (lon, lat), srid=4326)
        geoareas = cls.objects.all().order_by('area')
        for geoarea in geoareas:
            polygon = GEOSGeometry(geoarea.geographic_polygon, srid=4326)
            if polygon.contains(point):
                return geoarea
        return None


class District(BaseModel):
    """
    Район города.
    """
    geographic_area = models.ForeignKey(GeographicArea, verbose_name=u'город')
    name = models.CharField(u'название', max_length=255)
    geographic_polygon = models.TextField(u'полигон')  # format: "POLYGON((<longitude> <latitude>,...))"
    country = models.CharField(u'страна', max_length=255, default=u'Россия', blank=True)
    adm_area_level_1 = models.CharField(u'административно-территориальная единица верхнего уровня', max_length=255, default='', blank=True, help_text=u'Республика, область, край и т.п.')
    adm_area_level_2 = models.CharField(u'административно-территориальная единица низшего уровня', max_length=255, default='', blank=True, help_text=u'Район и т.п.')

    class Meta:
        verbose_name = u'Район'
        verbose_name_plural = u'Районы'

    def __unicode__(self):
        return self.name


class BasePlace(models.Model):
    """
    Базовая модель места.
    """
    name = models.CharField(u'название', max_length=255, default='', blank=True)
    address = models.CharField(u'адрес', max_length=255, default='', blank=True)
    latitude = models.FloatField(u'широта', blank=True)
    longitude = models.FloatField(u'долгота', blank=True)
    postal_code = models.CharField(u'почтовый индекс', max_length=255, default='', blank=True)
    country = models.CharField(u'страна', max_length=255, default='', blank=True)
    adm_area_level_1 = models.CharField(u'административно-территориальная единица верхнего уровня', max_length=255, default='', blank=True, help_text=u'Республика, область, край и т.п.')
    adm_area_level_2 = models.CharField(u'административно-территориальная единица низшего уровня', max_length=255, default='', blank=True, help_text=u'Район и т.п.')
    locality = models.CharField(u'населённый пункт', max_length=255, default='', blank=True)
    street = models.CharField(u'улица', max_length=255, default='', blank=True)
    house = models.CharField(u'дом', max_length=255, default='', blank=True)
    porch = models.CharField(u'подъезд', max_length=255, default='', blank=True)
    geographic_area = models.ForeignKey(GeographicArea, verbose_name=u'географическая область', null=True, blank=True)
    district = models.ForeignKey(District, blank=True, null=True)

    class Meta:
        abstract = True

    def __unicode__(self):
        if self.name:
            return self.name
        elif self.address:
            return self.address
        else:
            return u'%f, %f' % (self.latitude, self.longitude)

    def get_geographic_area(self):
        """
        Возвращает геообласть, к которой относится место.
        """
        if not self.latitude or not self.longitude:
            return None
        point = GEOSGeometry('POINT(%s %s)' % (self.longitude, self.latitude), srid=4326)
        areas = GeographicArea.objects.all().order_by('area')
        for area in areas:
            polygon = GEOSGeometry(area.geographic_polygon, srid=4326)
            if polygon.contains(point):
                return area

    def get_locality_as_hashtag(self):
        return string_to_hashtag(self.locality)

    def get_clean_locality(self):
        return self.locality.replace(u'Г.', '').replace(u'г.', '').replace(u'город', '').replace(u'Город', '').strip()

    def save(self, *args, **kwargs):
        if self.district:
            polygon = GEOSGeometry(self.district.geographic_polygon, srid=4326)
            self.latitude = polygon.centroid.x
            self.longitude = polygon.centroid.y
            self.name = self.district.name
            self.country = self.district.country
            self.adm_area_level_1 = self.district.adm_area_level_1
            self.adm_area_level_2 = self.district.adm_area_level_2
            self.locality = self.district.geographic_area.name
            self.street = ''
            self.house = ''
            self.porch = ''
            address_components = [
                self.country,
                self.adm_area_level_1,
                self.locality,
                self.name,
            ]
            self.address = ', '.join(filter(None, address_components))
        elif not self.address:
            address_components = [
                self.postal_code,
                self.country,
                self.adm_area_level_1,
                self.locality,
                self.street,
                self.house,
            ]
            self.address = ', '.join(filter(None, address_components))
        self.geographic_area = self.get_geographic_area()
        super(BasePlace, self).save(*args, **kwargs)


class PlaceLocalization(models.Model):
    """
    Модель локализации места
    """
    place_id = models.ForeignKey('Place', blank=True, null=True)
    localization = models.CharField(u'код языка', default='', blank=True, max_length=2)
    country = models.CharField(u'страна', max_length=255, default='', blank=True)
    adm_area_level_1 = models.CharField(u'административно-территориальная единица верхнего уровня', max_length=255, default='', blank=True, help_text=u'Республика, область, край и т.п.')
    adm_area_level_2 = models.CharField(u'административно-территориальная единица низшего уровня', max_length=255, default='', blank=True, help_text=u'Район и т.п.')
    locality = models.CharField(u'населённый пункт', max_length=255, default='', blank=True)
    street = models.CharField(u'улица', max_length=255, default='', blank=True)
    house = models.CharField(u'дом', max_length=255, default='', blank=True)

    def __unicode__(self):
        if self.locality and self.street:
            return u' '.join([self.locality, self.street])
        else:
            try:
                return self.place_id.__unicode__()
            except AttributeError:
                return u''


class Place(BasePlace):
    """
    Место, точка маршрута.
    """
    user = models.ForeignKey(User)
    last_ride = models.DateTimeField(blank=True, null=True, verbose_name=u'дата последней поездки')

    @property
    def routes(self):
        """
        Отсортированный по дате поездки список маршрутов, в которых фигурирует место.
        """
        instances = PlaceInRoute.objects.filter(place=self)
        routes = [instance.route for instance in instances]
        return sorted(routes, key=lambda route: route.departure_time, reverse=True)

    def save(self, *args, **kwargs):
        if not self.last_ride:
            self.last_ride = timezone.now()
        super(Place, self).save(*args, **kwargs)

    @classmethod
    def localize_place_dict(cls, place_dict, loc):
        """
        Локализирует место, представленное в виде словаря.
        Если запрашиваемой локализации нет, то возвращает транслит.
        """
        if loc == 'ru':
            return place_dict
        keys = [
            'country',
            'adm_area_level_1',
            'adm_area_level_2',
            'locality',
            'street',
            'house',
        ]
        try:
            place = cls.objects.get(id=place_dict['id'])
            l = PlaceLocalization.objects.get(place_id=place, localization=loc)
            for key in keys:
                if key in place_dict:
                    place_dict[key] = l.__getattribute__(key) or ''
            if 'address' in place_dict:
                address_components = [
                    place.postal_code,
                    l.country,
                    l.adm_area_level_1,
                    l.locality,
                    l.street,
                    l.house,
                ]
                place_dict['address'] = ', '.join(filter(None, address_components))
        except:
            for key in keys:
                if key in place_dict:
                    place_dict[key] = translit(place_dict[key], 'ru', reversed=True)
            if 'address' in place_dict:
                place_dict['address'] = translit(place_dict['address'], 'ru', reversed=True)
        return place_dict


class PopularPlace(BasePlace):
    """
    Популярное место.
    """
    description = models.CharField(u'описание', max_length=255, default='', blank=True)


class Tariff(BaseModel):
    MARKUP_TYPES = (
        (u'absolute', u'Абсолютная'),
        (u'relative', u'Относительная'),
    )
    name = models.CharField(u'название', max_length=100)
    is_default = models.BooleanField(u'тариф по умолчанию', blank=True, default=False)
    cost_round = models.IntegerField(u'округление стоимости', blank=True, default=0)
    waiting_downtime_free_minutes = models.IntegerField(u'количество бесплатных минут простоя при ожидании клиента', blank=True, default=0)
    waiting_downtime_minute_cost = models.FloatField(u'цена за минуту простоя при ожидании клиента', blank=True, default=0)
    in_way_downtime_free_minutes = models.IntegerField(u'количество бесплатных минут простоя в пути с клиентом', blank=True, default=0)
    in_way_downtime_minute_cost = models.FloatField(u'цена за минуту простоя в пути с клиентом', blank=True, default=0)
    in_way_stop_cost = models.FloatField(u'стоимость остановки в пути с клиентом', blank=True, default=0)
    min_order_cost = models.FloatField(u'минимальная стоимость заказа', blank=True, default=0)
    landing_cost = models.FloatField(u'цена посадки', blank=True, default=0)
    km_in_city_cost = models.FloatField(u'стоимость км в городе', blank=True, default=0)
    km_out_city_cost = models.FloatField(u'стоимость км за городом', blank=True, default=0)
    is_discount_to_min_order_cost_enable = models.BooleanField(u'применяется ли скидка на минимальную стоимость заказа', blank=True, default=False)
    is_traffic_jam_mode_enable = models.BooleanField(u'доступен ли режим пробки', blank=True, default=False)
    traffic_jam_minute_cost = models.FloatField(u'цена за минуту в режиме пробки', blank=True, default=0)
    traffic_jam_speed = models.FloatField(u'скорость авто, при которой включается режим пробки (км/ч)', blank=True, default=0)
    traffic_jam_time = models.IntegerField(u'время, которое авто должно ехать с указанной скоростью для включения режима пробки (сек.)', blank=True, default=0)
    markup_type = models.CharField(u'тип наценки', max_length=50, choices=MARKUP_TYPES, blank=True, default=u'absolute')
    markup_baby_chair = models.FloatField(u'наценка за детское кресло', max_length=30, blank=True, default=0)
    markup_conditioner = models.FloatField(u'наценка за кондиционер', blank=True, default=0)
    markup_animals = models.FloatField(u'наценка за перевозку животных', blank=True, default=0)
    markup_smoking = models.FloatField(u'наценка за курение в машине', blank=True, default=0)
    markup_check_printing = models.FloatField(u'наценка за печать чека', blank=True, default=0)
    weekdays = models.CharField(u'дни недели, по которым действует тариф', help_text=u'0 - понедельник', max_length=14, blank=True, default=u'0,1,2,3,4,5,6')
    begin_time = models.TimeField(u'время начала действия тарифа', blank=True, null=True)
    end_time = models.TimeField(u'время окончания действия тарифа', blank=True, null=True)
    begin_date = models.DateField(u'дата начала действия тарифа', blank=True, null=True)
    end_date = models.DateField(u'дата окончания действия тарифа', blank=True, null=True)
    priority = models.IntegerField(u'приоритет тарифа', help_text=u'чем больше, тем важнее', blank=True, default=0)

    class Meta:
        verbose_name = u'Тариф'
        verbose_name_plural = u'Тарифы'

    def __unicode__(self):
        return self.name


class RouteManager(models.Manager):
    def create_route(self, user, role, places, **kwargs):
        """
        Most convenient way to create routes.
        :param user:
        :param role:
        :param places:
        :param organization:
        :param departure_time:
        :param waiting_time_span:
        :param passengers_count:
        :param cost:
        :param walking_distance:
        :param distance_extension:
        :param match_waiting_time:
        :param regular_route:
        :param recurrence:
        :param accept_carpool:
        :param accept_taxi:
        :param accept_bus:
        :param search_friends:
        :param kwargs:
        :return:
        """
        defaults = {
            'departure_time': timezone.now(),
            'waiting_time_span': 0,
            'passengers_count': 0,
            'cost': 0,
            'walking_distance': 0,
            'distance_extension': 0,
            'accept_carpool': False,
            'accept_taxi': False,
            'accept_bus': False,
            'search_friends': False,
        }
        data = defaults
        data.update(kwargs)
        r = Route(user=user, role=role, places=places, **data)
        r.save()
        return r


ROUTE_STATUS_CHOICES = (
    ('active', _(u'активный')),
    ('canceled', _(u'отменённый')),
    ('done', _(u'завершённый')),
)


class Route(models.Model):
    """Маршрут."""
    user = models.ForeignKey(User)
    organization = models.ForeignKey(Organization, blank=True, null=True, related_name='routes')
    role = models.CharField(max_length=9, choices=ROLE_CHOICES, verbose_name=u'роль')
    departure_time = models.DateTimeField(verbose_name=u'время отправления')
    waiting_time_span = models.IntegerField(verbose_name=u'время ожидания в пути, мин.')
    passengers_count = models.IntegerField(blank=True, null=True, verbose_name=u'количество пассажирских мест')
    cost = models.DecimalField(blank=True, null=True, max_digits=11, decimal_places=2, verbose_name=u'стоимость')
    walking_distance = models.IntegerField(blank=True, null=True, verbose_name=u'максимальная дистанция до места посадки, м')
    distance_extension = models.FloatField(blank=True, null=True, verbose_name=u'коэффициент максимального увеличение длины пути')
    match_waiting_time = models.DateTimeField(blank=True, null=True, verbose_name=u'время ожидания подбора попутчиков')
    date_created = models.DateTimeField(verbose_name=u'время создания маршрута', blank=True, null=True, editable=False)
    date_modified = models.DateTimeField(verbose_name=u'время изменения маршрута', blank=True, null=True, editable=False)
    regular_route = models.ForeignKey('self', verbose_name=u'экземпляры маршрута', related_name='occurrences', blank=True, null=True)
    recurrence = models.OneToOneField(Recurrence, verbose_name=u'правило повтора поездки', blank=True, null=True)
    last_occurrence_time = models.DateTimeField(verbose_name=u'время последней поездки регулярного маршрута', blank=True, null=True)
    accept_carpool = models.BooleanField(_(u'искать попутку'), blank=True, default=True)
    accept_taxi = models.BooleanField(_(u'искать такси'), blank=True, default=False)
    accept_bus = models.BooleanField(_(u'искать автобус'), blank=True, default=False)
    search_friends = models.BooleanField(_(u'искать только друзей'), blank=True, default=False)
    status = models.CharField(u'статус маршрута', choices=ROUTE_STATUS_CHOICES, max_length=20, default='active', blank=True)
    comment = models.CharField(u'комментарий', max_length=255, blank=True, default='')
    is_intercity = models.NullBooleanField(u'междугородний маршрут', blank=True)
    char_id = models.CharField(u'символьный ID', max_length=20, blank=True, null=True)
    start_place = models.ForeignKey(Place, related_name=u'start_place_route', blank=True, null=True)
    finish_place = models.ForeignKey(Place, related_name=u'finish_place_route', blank=True, null=True)
    driver_route = models.ForeignKey('self', blank=True, null=True)
    consumer = models.CharField(max_length=50, choices=CONSUMERS, blank=True, default='vputi')
    car_baby_chair = models.CharField(u'детское кресло', max_length=30, blank=True, default='')  # 0, 0+, 1, 2, 3
    car_conditioner = models.BooleanField(u'кондиционер', blank=True, default=False)
    car_animals = models.BooleanField(u'перевозка животных', blank=True, default=False)
    car_smoking = models.BooleanField(u'курение в машине', blank=True, default=False)
    car_check_printing = models.BooleanField(u'печать чека', blank=True, default=False)
    car_large_trunk = models.BooleanField(u'большой багаж', blank=True, default=False)
    car_is_large = models.BooleanField(verbose_name=u'в машине 5+ мест', blank=True, default=False)
    deaf_mute = models.BooleanField(verbose_name=u'глухонемой', blank=True, default=False)
    tariff = models.ForeignKey(Tariff, blank=True, null=True)

    objects = RouteManager()
    _places_updated = False

    @property
    def places(self):
        if not hasattr(self, '_places'):
            self._places = list(Place.objects.filter(placeinroute__route=self).order_by('placeinroute__index'))
        return self._places

    @places.setter
    def places(self, value):
        self._places_updated = True
        self._places = value

    @places.deleter
    def places(self):
        if hasattr(self, '_places'):
            self._places_updated = True
            del self._places

    def __unicode__(self):
        out_tuple = ('?', '?')
        places = self.places
        if len(places) > 1:
            out_tuple = (places[0], places[-1])
        elif len(places) == 1:
            out_tuple = (places[0], '?')
        return u'%s - %s' % out_tuple

    def clean(self):
        from django.core.exceptions import ValidationError
        # Если role = driver, то passengers_count и distance_extension должны иметь значение.
        if self.role == 'driver':
            if not self.passengers_count:
                raise ValidationError(u'Passengers count for driver may not be blank or 0.')
            elif self.passengers_count < 0:
                raise ValidationError(u'Passengers count must be positive integer value.')

            if self.distance_extension is None and self.distance_extension != 0:
                raise ValidationError(u'Distance extension for driver may not be blank.')
            elif self.distance_extension < 0:
                raise ValidationError(u'Distance extension must be positive floating point value or 1.')

        # Если role = driver, то passengers_count и distance_extension должны иметь значение.
        elif self.role == 'passenger':
            if self.walking_distance is None and self.walking_distance != 0:
                raise ValidationError(u'Walking distance for passenger may not be blank.')
            elif self.walking_distance < 0:
                raise ValidationError(u'Walking distance must be positive integer value or 0.')

    def save(self, send_to_matcher=True, *args, **kwargs):
        t = timezone.now()
        if not self.date_created:
            self.date_created = t
        self.date_modified = t
        if not self.last_occurrence_time:
            self.last_occurrence_time = self.departure_time

        if self.role == 'passenger':
            self.cost = self.calculate_route_cost(is_carpool=True)

        if not self.char_id:
            self.char_id = self.generate_char_id()

        # определяем межгород
        start_locality = self.places[0].locality if len(self.places) > 0 else None
        finish_locality = self.places[-1].locality if len(self.places) > 1 else None
        if start_locality and finish_locality:
            self.is_intercity = True if start_locality != finish_locality else False

        # дублируем начальную и конечную точку напрямую в маршрут
        self.start_place = self.places[0] if len(self.places) > 0 else None
        self.finish_place = self.places[-1] if len(self.places) > 1 else None

        # если мест меньше двух, то слать маршрут в матчер бесмысленно
        if len(self.places) < 2:
            send_to_matcher = False

        # если это пассажирский таксишный маршрут, назначаем ему тариф
        if self.accept_taxi and self.role == u'passenger' and not self.tariff:
            self.tariff = self.choose_tariff()

        self.send_to_matcher = send_to_matcher

        super(self.__class__, self).save(*args, **kwargs)

    def save_base(self, raw=False, cls=None, origin=None, force_insert=False,
                  force_update=False, using=None):
        """
        Does the heavy-lifting involved in saving. Subclasses shouldn't need to
        override this method. It's separate from save() in order to hide the
        need for overrides of save() to pass around internal-only parameters
        ('raw', 'cls', and 'origin').
        """
        using = using or router.db_for_write(self.__class__, instance=self)
        assert not (force_insert and force_update)
        if cls is None:
            cls = self.__class__
            meta = cls._meta
            if not meta.proxy:
                origin = cls
        else:
            meta = cls._meta

        if origin and not meta.auto_created:
            signals.pre_save.send(sender=origin, instance=self, raw=raw, using=using)

        # If we are in a raw save, save the object exactly as presented.
        # That means that we don't try to be smart about saving attributes
        # that might have come from the parent class - we just save the
        # attributes we have been given to the class we have been given.
        # We also go through this process to defer the save of proxy objects
        # to their actual underlying model.
        if not raw or meta.proxy:
            if meta.proxy:
                org = cls
            else:
                org = None
            for parent, field in meta.parents.items():
                # At this point, parent's primary key field may be unknown
                # (for example, from administration form which doesn't fill
                # this field). If so, fill it.
                if field and getattr(self, parent._meta.pk.attname) is None and getattr(self, field.attname) is not None:
                    setattr(self, parent._meta.pk.attname, getattr(self, field.attname))

                self.save_base(cls=parent, origin=org, using=using)

                if field:
                    setattr(self, field.attname, self._get_pk_val(parent._meta))
            if meta.proxy:
                return

        if not meta.proxy:
            non_pks = [f for f in meta.local_fields if not f.primary_key]

            # First, try an UPDATE. If that doesn't update anything, do an INSERT.
            pk_val = self._get_pk_val(meta)
            pk_set = pk_val is not None
            record_exists = True
            manager = cls._base_manager
            if pk_set:
                # Determine whether a record with the primary key already exists.
                if (force_update or (not force_insert and
                                     manager.using(using).filter(pk=pk_val).exists())):
                    # It does already exist, so do an UPDATE.
                    if force_update or non_pks:
                        values = [(f, None, (raw and getattr(self, f.attname) or f.pre_save(self, False))) for f in non_pks]
                        if values:
                            rows = manager.using(using).filter(pk=pk_val)._update(values)
                            if force_update and not rows:
                                raise DatabaseError("Forced update did not affect any rows.")
                else:
                    record_exists = False
            if not pk_set or not record_exists:
                if meta.order_with_respect_to:
                    # If this is a model with an order_with_respect_to
                    # autopopulate the _order field
                    field = meta.order_with_respect_to
                    order_value = manager.using(using).filter(**{field.name: getattr(self, field.attname)}).count()
                    self._order = order_value

                fields = meta.local_fields
                if not pk_set:
                    if force_update:
                        raise ValueError("Cannot force an update in save() with no primary key.")
                    fields = [f for f in fields if not isinstance(f, AutoField)]

                record_exists = False

                update_pk = bool(meta.has_auto_field and not pk_set)
                result = manager._insert([self], fields=fields, return_id=update_pk, using=using, raw=raw)

                if update_pk:
                    setattr(self, meta.pk.attname, result)
            transaction.commit_unless_managed(using=using)

        # Store the database on which the object was saved
        self._state.db = using
        # Once saved, this is no longer a to-be-added instance.
        self._state.adding = False

        # save places
        if self._places_updated:
            if [p.id for p in self.places] != [Place.objects.filter(placeinroute__route=self).order_by('placeinroute__index').values_list('id', flat=True)]:
                PlaceInRoute.objects.filter(route=self).delete()
                for i in range(len(self.places)):
                    PlaceInRoute.objects.create(index=i, route=self, place=self.places[i])

        # Signal that the save is complete
        if origin and not meta.auto_created:
            signals.post_save.send(sender=origin, instance=self, created=(not record_exists), raw=raw, using=using)

    def cancel(self, send_to_matcher=True):
        """
        Отменяет маршрут.
        """
        self.status = 'canceled'
        self.save(send_to_matcher=send_to_matcher)

        # если это родительский регулярный маршрут, то отменяем все его активные инстансы
        if self.recurrence:
            Route.objects.filter(regular_route=self, status='active').update(status='canceled')

    def get_route_distance(self, service='google'):
        """
        Возвращает расстояние маршрута, рассчитанное с помощью одного из сервисов (google, osrm), в метрах.
        """
        try:
            start_place = self.places[0]
            finish_place = self.places[-1]
        except IndexError:
            return 0

        if service == 'google':
            params = {
                'origins': '%s,%s' % (start_place.latitude, start_place.longitude),
                'destinations': '%s,%s' % (finish_place.latitude, finish_place.longitude),
                'mode': 'driving',
                'sensor': 'false',
            }
            url = 'http://maps.googleapis.com/maps/api/distancematrix/json'
            try:
                response = requests.get(url, params=params)
                response = response.json()
                distance = response['rows'][0]['elements'][0]['distance']['value']
                return distance
            except:
                return 0
        elif service == 'osrm':
            params = (start_place.latitude, start_place.longitude, finish_place.latitude, finish_place.longitude)
            url = 'http://193.218.136.152/viaroute?loc=%s,%s&loc=%s,%s&alt=false&instructions=false' % params
            try:
                response = requests.get(url)
                response = response.json()
                distance = response['route_summary']['total_distance']
                return distance
            except:
                return 0
        else:
            return 0

    def calculate_route_cost(self, is_carpool=False):
        """
        Расчитывает стоимость маршрута.
        """
        distance = self.get_route_distance() / 1000.0

        if distance > DEFAULT_ROUTE_DISTANCE:
            cost = DEFAULT_ROUTE_COST + OVER_ROUTE_DISTANCE_PRICE * (distance - DEFAULT_ROUTE_DISTANCE)
            cost = int(round(cost))
        else:
            cost = DEFAULT_ROUTE_COST

        if is_carpool:
            cost *= CARPOOL_COEFFICIENT
            cost = math.ceil(cost / 10.0) * 10

        return cost

    def get_webapp_link(self, vk=True):
        if vk:
            base_url = 'https://vk.com/app2370553_101413049'
        else:
            base_url = 'https://web.ktovputi.ru'
        hash_tpl = 'sp=%(sp_lat)s,%(sp_lon)s&fp=%(fp_lat)s,%(fp_lon)s&dt=%(dt)s&wts=%(wts)s&rl=%(role)s&rid=%(rid)s'
        hash_context = {
            'sp_lat': self.places[0].latitude,
            'sp_lon': self.places[0].longitude,
            'fp_lat': self.places[-1].latitude,
            'fp_lon': self.places[-1].longitude,
            'dt': format(self.departure_time, 'c'),
            'wts': self.waiting_time_span,
            'role': 'driver' if self.role == 'passenger' else 'passenger',  # роль ставим противоположную данному маршруту
            'rid': self.id,
        }
        hash_str = urllib2.quote(hash_tpl % hash_context)
        link = '%s#%s' % (base_url, hash_str)
        return link

    def get_short_link(self, vk=True):
        if not self.char_id:
            self.char_id = self.generate_char_id()
            self.save(send_to_matcher=False)
        domain = settings.SHORT_DOMAIN_VK if vk else settings.SHORT_DOMAIN_WEB
        return '%s/z%s' % (domain, self.char_id)

    def get_recurrence_as_str(self):
        recurrence = self.regular_route.recurrence.recurrence if self.regular_route else self.recurrence.recurrence
        recurrence = serialize(recurrence).split('BYDAY=')[1].split(',')
        week_days = {'MO': u'Пн', 'TU': u'Вт', 'WE': u'Ср', 'TH': u'Чт', 'FR': u'Пт', 'SA': u'Сб', 'SU': u'Вс'}
        recurrence = [week_days[day] for day in recurrence]
        recurrence = ', '.join(recurrence)
        return recurrence

    def create_tweet(self):
        """
        Создает твит о маршруте.
        """
        tag = u'Подвезу' if self.role == 'driver' else u'ИщуПопутку'

        start_place = self.places[0]
        finish_place = self.places[-1]
        if not start_place.locality or not finish_place.locality:
            return False
        start = start_place.get_locality_as_hashtag()
        finish = finish_place.get_locality_as_hashtag()

        if self.regular_route or self.recurrence:
            date = self.get_recurrence_as_str()
        else:
            date = format(self.departure_time, 'd E')

        link = self.get_short_link(vk=False)
        if link:
            link = u'Отозваться: ' + link + u'\nДругие: https://web.ktovputi.ru'
        else:
            link = u'Этот и другие маршруты: https://web.ktovputi.ru'

        msg_tpl = u'#%(tag)s\nОт: %(start)s\nДо: %(finish)s\nКогда: %(date)s\n%(link)s'
        msg_params = {
            'tag': tag,
            'start': start,
            'finish': finish,
            'date': date,
            'link': link,
        }
        msg = msg_tpl % msg_params
        return create_tweet(msg)

    def create_selective_tweet(self):
        """
        Создает твит, только если маршрут междугородний и включает один из указанных городов.
        """
        cities = [
            u'москва',
            u'санкт-петербург',
            u'красноярск',
            u'новосибирск',
            u'краснодар',
            u'екатеринбург',
            u'казань',
            u'уфа',
            u'киев',
        ]

        # постить в твиттер не чаще одного раза в час
        now = timezone.now()
        last_tweet = Param.get_last_tweet_date()
        if not last_tweet:
            return False
        if now - last_tweet < timedelta(hours=1):
            return False

        start = self.places[0].get_clean_locality().lower()
        finish = self.places[-1].get_clean_locality().lower()

        # маршруты должен быть: междугородний, разовый, включать один из заданных городов
        if start == finish:
            return False
        if self.recurrence or self.regular_route:
            return False
        if not start in cities and not finish in cities:
            return False

        # делаем твит, запоминаем дату
        result = self.create_tweet()
        if result:
            Param.set_last_tweet_date(now)
        return result

    def create_regular_instance(self):
        """
        Создает экземпляр регулярного маршрута.
        """
        if not self.recurrence:
            return None

        waiting_for_time = self.last_occurrence_time + timedelta(minutes=self.waiting_time_span) + timedelta(minutes=30)
        if waiting_for_time >= timezone.now():
            return None

        next_departure_time = self.recurrence.recurrence.after(timezone.now())
        if not next_departure_time:
            return None

        r = Route.objects.create_route(
            user=self.user,
            role=self.role,
            departure_time=next_departure_time,
            waiting_time_span=self.waiting_time_span,
            passengers_count=self.passengers_count,
            cost=self.cost,
            walking_distance=self.walking_distance,
            distance_extension=self.distance_extension,
            places=self.places,
            match_waiting_time=self.match_waiting_time,
            regular_route=self,
            accept_carpool=self.accept_carpool,
            accept_taxi=self.accept_taxi,
            accept_bus=self.accept_bus,
        )
        self.last_occurrence_time = next_departure_time
        self.save()
        return r

    def generate_char_id(self):
        chars = string.lowercase + string.uppercase + string.digits
        i = 0
        max = 10000000
        while i < max:
            char_id = ''.join(random.choice(chars) for x in range(8))
            if not Route.objects.filter(char_id=char_id):
                return char_id
            i += 1
        raise Exception('All route char_ids are taken')

    @classmethod
    def get_active_routes(cls, role='driver', min_time_span=None, max_time_span=None, accept_taxi=False,
                          add_params=None, order_by=None, limit=10, offset=0, consumer='vputi'):
        """
        time_span - если параметр указан, то будут возвращены только маршруты со временем выезда < now + time_span,
        указывается в минутах
        """
        max_time_span = int_or_none(max_time_span)
        min_time_span = int_or_none(min_time_span)
        limit = int_or_none(limit)
        offset = int_or_none(offset)
        params = {
            'role': role,
            'accept_taxi': accept_taxi,
            'status': 'active',
            'driver_route__isnull': True,
            'consumer': consumer,
        }
        if min_time_span:
            dt_max = timezone.now() + timedelta(minutes=min_time_span)
            params['departure_time__gte'] = dt_max
        if max_time_span:
            dt_max = timezone.now() + timedelta(minutes=max_time_span)
            params['departure_time__lte'] = dt_max
        add_args = []
        if add_params:
            for k, v in add_params.copy().iteritems():
                if ((v is True) and (role == 'passenger')) or (((v is False) or (v == u'')) and (role == 'driver')):
                    del add_params[k]
                elif (type(v) == unicode) and (role == 'passenger'):
                    # This is okay even with empty string
                    add_args.append(Q(**{k: v}) | Q(**{k: u''}) | Q(**{k: 'null'}))
                    del add_params[k]
            params.update(add_params)
        if not order_by:
            order_by = ['-departure_time']
        routes = cls.objects.filter(*add_args, **params).order_by(*order_by)[offset:offset + limit]
        return routes

    @classmethod
    def get_active_routes_by_locality(cls, role='driver', min_time_span=None, max_time_span=None, accept_taxi=False,
                                      sp_locality=None, fp_locality=None, add_params=None, order_by=None,
                                      limit=10, offset=0, consumer='vputi'):
        """
        Возвращает активные маршруты, у которых начальный и/или конечный locality включает переданные значения.
        """
        if not sp_locality and not fp_locality:
            return None

        if sp_locality:
            add_params['start_place__locality__icontains'] = sp_locality
        if fp_locality:
            add_params['finish_place__locality__icontains'] = fp_locality
        routes = cls.get_active_routes(role, min_time_span, max_time_span, accept_taxi, add_params, order_by,
                                       limit, offset, consumer)
        return routes

    @classmethod
    def km_to_coords_dt(cls, value):
        """
        Конвертирует километры в смещение по координатам.
        value должен быть целочисленным
        """
        try:
            value = int(value)
            dt = 0
            for i in range(0, value):
                dt += 0.005
            return dt
        except:
            return 0

    @classmethod
    def get_active_routes_by_coords(cls, role='driver', min_time_span=None, max_time_span=None, accept_taxi=False,
                                    sp_lat=None, sp_lon=None, fp_lat=None, fp_lon=None, radius=2, add_params=None,
                                    order_by=None, limit=10, offset=0, consumer='vputi'):
        """
        Возвращает активные маршруты, у которых начальная и/или конечная точка находятся в заданных пределах.
        radius указывается в километрах только целыми числами
        """
        sp_lat = to_float_or_none(sp_lat)
        sp_lon = to_float_or_none(sp_lon)
        fp_lat = to_float_or_none(fp_lat)
        fp_lon = to_float_or_none(fp_lon)

        # проверяем, чтобы пары координаты координат были полными
        if (sp_lat and not sp_lon) or (not sp_lat and sp_lon):
            return None
        if (fp_lat and not fp_lon) or (not fp_lat and fp_lon):
            return None
        if not sp_lat and not sp_lon and not fp_lat and not fp_lon:
            return None

        coords_dt = cls.km_to_coords_dt(radius)
        if sp_lat and sp_lon:
            add_params['start_place__latitude__lte'] = sp_lat + coords_dt
            add_params['start_place__latitude__gte'] = sp_lat - coords_dt
            add_params['start_place__longitude__lte'] = sp_lon + coords_dt
            add_params['start_place__longitude__gte'] = sp_lon - coords_dt
        if fp_lat and fp_lon:
            add_params['finish_place__latitude__lte'] = fp_lat + coords_dt
            add_params['finish_place__latitude__gte'] = fp_lat - coords_dt
            add_params['finish_place__longitude__lte'] = fp_lon + coords_dt
            add_params['finish_place__longitude__gte'] = fp_lon - coords_dt
        routes = cls.get_active_routes(role, min_time_span, max_time_span, accept_taxi, add_params, order_by,
                                       limit, offset, consumer)
        return routes

    @classmethod
    def get_taxi_routes(cls, sp_lat=None, sp_lon=None, limit=10, offset=0):
        """
        Возвращает таксишные маршруты:
        1. Начальная точка которых находится в пределах 5 км от переданных координат и время выезда не позже, чем
        через 40 минут.
        2. Начальная точка которых находится в пределах 70 км от переданных координат и время выезда позже, чем
        через 40 минут (отложенные маршруты).
        """
        sp_lat = to_float_or_none(sp_lat)
        sp_lon = to_float_or_none(sp_lon)
        if not sp_lat or not sp_lon:
            return None

        near_dt = cls.km_to_coords_dt(5)
        far_dt = cls.km_to_coords_dt(70)
        routes = cls.objects.filter(
            Q(
                accept_taxi=True,
                role='passenger',
                status='active',
                driver_route__isnull=True,
                departure_time__gt=timezone.now(),
                departure_time__lt=timezone.now() + timedelta(minutes=40),
                start_place__latitude__lte=sp_lat + near_dt,
                start_place__latitude__gte=sp_lat - near_dt,
                start_place__longitude__lte=sp_lon + near_dt,
                start_place__longitude__gte=sp_lon - near_dt,
            ) | Q(
                accept_taxi=True,
                role='passenger',
                status='active',
                driver_route__isnull=True,
                departure_time__gt=timezone.now() + timedelta(minutes=40),
                start_place__latitude__lte=sp_lat + far_dt,
                start_place__latitude__gte=sp_lat - far_dt,
                start_place__longitude__lte=sp_lon + far_dt,
                start_place__longitude__gte=sp_lon - far_dt,
            )
        ).order_by('-date_created')[offset:offset + limit]
        return routes

    def choose_tariff(self):
        """
        Возвращает подходящий маршруту тариф.
        """
        weekday = str(timezone.now().weekday())
        time = timezone.now().time()
        date = timezone.now().date()
        tariffs = Tariff.objects.filter(
            Q(begin_date__gte=date, end_date__lte=date, is_default=False) |
            Q(weekdays__contains=weekday, is_default=False) |
            Q(begin_time__gte=time, end_time__lte=time, is_default=False)
        ).order_by('-priority', 'begin_date', 'begin_time')
        # возвращаем первый тариф, для которого выполняются все указанные в нем условия
        for tariff in tariffs:
            if tariff.begin_date or tariff.end_date:
                if date < tariff.begin_date or date > tariff.end_date:
                    continue
            if tariff.begin_time or tariff.end_time:
                if time < tariff.begin_time or time > tariff.end_time:
                    continue
            if tariff.weekdays:
                if weekday not in tariff.weekdays:
                    continue
            return tariff
        # если не найдено подходящего тарифа, то возвращаем тариф по умолчанию
        tariffs = Tariff.objects.filter(is_default=True)
        return tariffs[0] or None


class PlaceInRoute(models.Model):
    """
    Место в маршруте.
    """
    place = models.ForeignKey(Place, verbose_name=u'место')
    route = models.ForeignKey(Route, verbose_name=u'маршрут')
    index = models.IntegerField(verbose_name=u'номер')

    def __unicode__(self):
        return u'%d: %s' % (self.index, self.place)

    def save(self, *args, **kwargs):
        self.place.last_ride = timezone.now()
        self.place.save()
        super(self.__class__, self).save(*args, **kwargs)


class Appointment(models.Model):
    """
    Место/время встречи/высадки
    """
    # lat = models.FloatField(u'широта')
    # lon = models.FloatField(u'долгота')
    # address = models.CharField(u'адрес', max_length=255, blank=True, default='')
    # time = models.DateTimeField(u'время', blank=True, null=True)
    name = models.CharField(u'название', max_length=255, blank=True, default='')
    time = models.DateTimeField(u'время', blank=True, null=True)


class RouteClick(models.Model):
    route = models.ForeignKey(Route, verbose_name=u'маршрут')
    date = models.DateTimeField(u'дата', auto_now_add=True)

    def __unicode__(self):
        return '%s - %s' % (self.route.id, self.date)


class RouteClicksStatManager(BaseManager):

    def add_click(self):
        """
        Добавляет клик в статистику для переданного шортлинка.
        Если для текущего месяца еще нет записи для данного шортлинка, то она создается и счетчик устанавливается на 1.
        Если для текущего месяца уже есть запись, то просто увеличивается счетчик переходов.
        """
        date = datetime.now().date()
        stat = self.all().order_by('-date')[:1]
        stat = stat[0] if stat else None
        # если нет ни одной статистики или нет статистики за текущий месяц, то создаем
        if not stat or stat.date.month != date.month or stat.date.year != date.year:
            stat = self.create(
                date=date,
                count=1,
            )
        else:
            stat.inc_count()
        return stat.count


class RoutesClicksStat(BaseDatedModel):
    date = models.DateField(u'дата')
    count = models.IntegerField(u'количество переходов', blank=True, default=0)

    objects = RouteClicksStatManager()

    class Meta:
        verbose_name = u'Статистика переходов '
        verbose_name_plural = u'Статистика переходов'

    def __unicode__(self):
        return 'stat %s by %s-%s' % (self.id, self.date.year, self.date.month)

    def inc_count(self):
        self.count += 1
        self.save()


MATCH_STATUS_CHOICES = (
    ('new', _(u'Новая')),
    ('accepted', _(u'Принята')),
    ('rejected', _(u'Отклонена')),
    ('done', _(u'Завершена')),  # поездка успешно завершена
)

MATCH_STATUS_WORKFLOW = {
    'new': ('new', 'accepted', 'rejected', 'done',),
    'accepted': ('accepted', 'rejected', 'done',),
    'rejected': ('rejected', 'accepted',),
    'done': ('done',),
}

# MATCH_STATUS_CHOICES = (
#     ('new', _(u'Новая')),
#     ('accepted', _(u'Принята')),
#     ('rejected', _(u'Отклонена')),
# )
#
# MATCH_STATUS_WORKFLOW = {
#     'new': ('new', 'accepted', 'rejected',),
#     'accepted': ('accepted', 'rejected',),
#     'rejected': ('rejected', 'accepted',),
# }


class MatchManager(models.Manager):
    pass


class Match(models.Model):
    """Совпадение маршрутов"""
    from_route = models.ForeignKey(Route, related_name='matches')
    to_route = models.ForeignKey(Route, related_name='matched')
    meeting = models.ForeignKey(Appointment, related_name='meeting_matches', verbose_name=u'место посадки')
    dropoff = models.ForeignKey(Appointment, related_name='dropoff_matches', verbose_name=u'место высадки')
    cost = models.DecimalField(u'стоимость', blank=True, null=True, max_digits=11, decimal_places=2)
    distance = models.IntegerField(u'длина маршрута, м')
    distance_extension = models.IntegerField(u'увеличение длины маршрута, м')
    status = models.CharField(u'статус подбора', choices=MATCH_STATUS_CHOICES, max_length=9, default='new', blank=True)
    to_status = models.CharField(u'статус симметричного подбора', choices=MATCH_STATUS_CHOICES, max_length=9, default='new', blank=True)
    rating = models.IntegerField(u'оценка поездки', default=0, blank=True)
    comment = models.CharField(u'комментарий', max_length=255, default='', blank=True)
    grade = models.FloatField(u'оценка совпадения маршрутов')
    detour = models.FloatField(u'величина отклонения')
    is_canceled = models.BooleanField(u'подбор отменён')
    is_driver_in_place = models.BooleanField(u'водитель на месте', blank=True, default=False)
    driver_in_place_time = models.DateTimeField(u'время приезда водителя', blank=True, null=True)
    is_passenger_sat = models.BooleanField(u'пассажир сел в авто', blank=True, default=False)


from apps.router.signal_handlers import *
