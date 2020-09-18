# -*- coding: utf-8 -*-
import random
import string

from django.contrib.contenttypes import generic
from django.db import models
from django.contrib.auth.models import User, Group
from django.contrib.staticfiles.storage import staticfiles_storage
from django.db.models import Avg
from piston.models import Consumer
from sorl.thumbnail import ImageField

from libs.config import BaseEnumerate
from libs.utils import format_filename
from libs.validators import validate_file_extension, validate_file_size
from apps.contacts.models import PhoneNumber, EmailAddress
from apps.operations.models import Operation
from apps.consumers.models import CONSUMERS, PLATFORMS, ConsumerVersions


__docformat__ = 'restructuredtext ru'


class DriverStatus(BaseEnumerate):
    """
    Driver status
    """

    OPEN = 'open'
    WORKING = 'working'
    CLOSED = 'closed'

    values = {
        OPEN:  u'Ожидает заказ',
        WORKING: u'Выполняет заказ',
        CLOSED: u'Не работает',
    }


def generate_username(length=8):
    chars = string.lowercase + string.digits
    i = 0
    MAX = 10000000
    while i < MAX:
        username = ''.join(random.choice(chars) for x in range(length))
        try:
            User.objects.get(username=username)
        except User.DoesNotExist:
            return username
        i += 1
    raise Exception('All random username are taken')


def create_account(phone):
    """
    Создаёт пользователя и привязывает к нему переданный номер телефона, если он есть.
    """
    user = User()
    user.username = generate_username()
    password = User.objects.make_random_password()
    user.set_password(password)
    user.save()
    if phone:
        PhoneNumber.objects.create(
            content_object=user.userprofile,
            phone_number=phone,
            is_verified=True,
            is_active=True,
            is_main=True,
        )
    return user


def get_or_create_account(phone):
    """
    Ищет пользователя по номеру телефона и возвращает его при успехе.
    Если пользователь не найден, то создаёт и возвращает нового пользователя.
    """
    user = User.objects.filter(
        userprofile__phones__phone_number=phone,
        userprofile__phones__is_verified=True,
        userprofile__phones__is_main=True,
        userprofile__phones__is_active=True,
    )
    if user:
        return user[0]
    else:
        return create_account(phone)


def get_image_name(instance, filename):
    return format_filename(filename, prefix='%s/' % '/'.join(['avatars', instance.user.username]))


class AppProfile(models.Model):
    user = models.ForeignKey(User)
    consumer = models.ForeignKey(Consumer)
    app_user_id = models.CharField(blank=False, max_length=32, verbose_name=u'id в соц. сети')

    def __unicode__(self):
        return self.app_user_id

    def save(self, *args, **kwargs):
        # удаляем все предыдущие app_profiles пользователя для данного consumer
        AppProfile.objects.filter(user=self.user, consumer=self.consumer).delete()

        # удаляем все app_profiles с таким app_user_id для данного consumer,
        # чтобы у нескольких пользователей не оказался одинаковый app_user_id
        AppProfile.objects.filter(consumer=self.consumer, app_user_id=self.app_user_id).delete()

        super(AppProfile, self).save(*args, **kwargs)


class UserProfile(models.Model):
    TAXI_STATUSES = (
        (u'open', u'ожидает заказ'),
        (u'working', u'выполняет заказ'),
        (u'closed', u'не работает'),
    )

    user = models.OneToOneField(User)

    last_name = models.CharField(u'фамилия', max_length=255, blank=True, default='')
    first_name = models.CharField(u'имя', max_length=255, blank=True, default='')
    middle_name = models.CharField(u'отчество', max_length=255, blank=True, default='')
    short_name = models.CharField(u'краткое имя', max_length=258, blank=True, default='')
    full_name = models.CharField(u'полное имя', max_length=765, blank=True, default='')

    # salutation = models.CharField(blank=True, default='', max_length=255, verbose_name=u'обращение')
    birth_date = models.DateField(u'дата рождения', blank=True, null=True)
    # TODO: Convert sex to CharField with choices 'male', 'female' and ''.
    sex = models.IntegerField(u'пол', blank=True, default=0)
    rank = models.CharField(u'ранг', max_length=32, blank=True)
    following_count = models.PositiveIntegerField(u'количество знакомых', blank=True, default=0)
    routes_count = models.PositiveIntegerField(u'количество зарегистрированных маршрутов', blank=True, default=0)
    image = ImageField(u'фото', upload_to=get_image_name, blank=True, null=True,
                       validators=[validate_file_extension, validate_file_size])
    phones = generic.GenericRelation(PhoneNumber)
    emails = generic.GenericRelation(EmailAddress)
    is_paid = models.BooleanField(u'платный аккаунт', blank=True, default=True)
    last_activity = models.DateTimeField(u'дата последней активности', blank=True, null=True)
    last_client_data = models.CharField(u'последний клиент', max_length=255, blank=True, null=True)
    last_consumer = models.CharField(max_length=50, choices=CONSUMERS, blank=True, default='gooto')
    last_platform = models.CharField(max_length=50, choices=PLATFORMS, blank=True, null=True)
    last_notice = models.DateTimeField(u'дата последнего напоминания', blank=True, null=True)
    is_frozen = models.BooleanField(u'заморожен', blank=True, default=False)
    rating = models.FloatField(u'рейтинг', blank=True, default=0)
    parent_phone = models.CharField(max_length=50, verbose_name=u'Телефон партнера', blank=True, null=True)

    # поля для такси
    car_brand = models.CharField(u'марка автомобиля', max_length=30, blank=True, default='')
    car_model = models.CharField(u'модель автомобиля', max_length=30, blank=True, default='')
    car_number = models.CharField(u'регистрационный номер', max_length=30, blank=True, default='')
    car_color = models.CharField(u'цвет автомобиля', max_length=30, blank=True, default='')
    car_landing_price = models.FloatField(u'цена посадки', blank=True, default=0)
    car_unit_price = models.FloatField(u'цена за единицу', blank=True, default=0)
    car_baby_chair = models.CharField(u'детское кресло', max_length=30, blank=True, default='')  # 0, 0+, 1, 2, 3
    car_conditioner = models.BooleanField(u'кондиционер', blank=True, default=False)
    car_animals = models.BooleanField(u'перевозка животных', blank=True, default=False)
    car_smoking = models.BooleanField(u'курение в машине', blank=True, default=False)
    car_check_printing = models.BooleanField(u'печать чека', blank=True, default=False)
    car_large_trunk = models.BooleanField(u'большой багаж', blank=True, default=False)
    car_is_large = models.BooleanField(verbose_name=u'в машине 5+ мест', blank=True, default=False)
    deaf_mute = models.BooleanField(verbose_name=u'глухонемой', blank=True, default=False)
    info = models.CharField(u'о себе', max_length=255, blank=True, default='')
    taxi_status = models.CharField(u'статус такси', max_length=30, choices=TAXI_STATUSES, blank=True, default=u'closed')

    lat = models.FloatField(u'текущая широта', blank=True, default=0)
    lon = models.FloatField(u'текущая долгота', blank=True, default=0)
    city = models.ForeignKey('router.GeographicArea', verbose_name=u'Текущий город', null=True)

    def __unicode__(self):
        return self.salutation

    def save(self, *args, **kwargs):
        from apps.router.models import GeographicArea
        self.full_name = u' '.join(filter(lambda s: s, [self.first_name, self.middle_name, self.last_name]))
        self.short_name = self.first_name
        if self.last_name:
            self.short_name = u'%s %s.' % (self.short_name, self.last_name[:1])
        if self.lat and self.lon:
            # Current city by coordinates
            self.city = GeographicArea.define_geographic_area(self.lat, self.lon)
        else:
            # TODO
            self.city_id = 1
        super(UserProfile, self).save(*args, **kwargs)

    def get_phone(self):
        if not hasattr(self, '_phone'):
            # Костыль для TMSRVR-140
            phones = PhoneNumber.objects.filter(object_id=self.pk).order_by('-is_active', '-is_main', '-date_modified')
            self._phone = phones[0] if phones else None

            # Как было раньше
            # try:
            #     self._phone = self.phones.get(is_active=True, is_main=True)
            # except (ObjectDoesNotExist, MultipleObjectsReturned):
            #     self._phone = None
        return self._phone

    def get_salutation(self):
        return self.first_name

    def set_salutation(self, value):
        self.first_name = value

    salutation = property(get_salutation, set_salutation)

    def get_image_url(self):
        if self.image:
            return self.image.url
        else:
            url = staticfiles_storage.url('avatars/default.png')
            return url

    def get_user_groups(self):
        return Group.objects.filter(user=self.user)

    def update_last_activity(self, request):
        self.last_activity = timezone.now()
        self.last_consumer = ConsumerVersions.define_consumer(request)
        self.last_platform = ConsumerVersions.define_platform(request)
        self.last_client_data = request.META['HTTP_USER_AGENT']
        self.save()
        if self.is_frozen:
            self.unfreeze()

    def freeze(self):
        from apps.router.models import Route

        # отменяем все активные разовые маршруты пользователя
        routes = Route.objects.filter(
            user=self.user,
            status='active',
            regular_route__isnull=True,
            recurrence__isnull=True,
        )
        for route in routes:
            route.cancel()

        self.is_frozen = True
        self.save()

    def unfreeze(self):
        from apps.router.models import Route

        now = timezone.now()

        # создаем экземпляры для всех регулярных маршрутов пользователя
        routes = Route.objects.filter(
            user=self.user,
            recurrence__dtend__gt=now,
            last_occurrence_time__lt=now,
        ).exclude(status='canceled')
        for route in routes:
            route.create_regular_instance()

        self.is_frozen = False
        self.save()

    def get_external_profiles(self):
        app_profiles = AppProfile.objects.filter(user=self.user)
        external_profiles = dict()
        for app_profile in app_profiles:
            external_profiles[app_profile.consumer.name] = app_profile.app_user_id
        return external_profiles

    def calculate_rating(self):
        """
        Рассчитывает рейтинг пользователя на основе оценок, выставленных ему попутчиками.
        """
        from apps.router.models import Match
        rating = Match.objects.filter(to_route__user=self.user, rating__gt=0).aggregate(Avg('rating'))['rating__avg']
        self.rating = rating or 0
        self.save()


from signal_handlers import *
