# -*- coding: utf-8 -*-
import dateutil.parser

import requests
from django import forms
from django.utils import timezone
from django.contrib.auth.models import User
from django.contrib.admin.widgets import AdminDateWidget
from django.forms.util import ErrorList
from django.utils.dateparse import parse_datetime
from sorl.thumbnail.fields import ImageFormField
from crispy_forms.helper import FormHelper
from datetimewidget.widgets import DateTimeWidget, DateWidget, TimeWidget
from piston.models import Consumer

from apps.accounts.models import UserProfile, AppProfile, generate_username, get_or_create_account
from apps.contacts.models import PhoneNumber
from apps.socnets.models import VKGroup
from apps.router.models import ROLE_CHOICES, Place
from apps.router.forms import RouteForm
from libs.validators import validate_file_extension, validate_file_size
from libs.yandex_geocode import get_coordinates_by_address
from libs.phones import format_phone


__docformat__ = 'restructuredtext ru'


class CrispyFormMixin(object):
    def __init__(self, *args, **kwargs):
        super(CrispyFormMixin, self).__init__(*args, **kwargs)
        self.helper = FormHelper()


class AvatarForm(forms.Form):
    image = ImageFormField(label=u'image', validators=[validate_file_extension, validate_file_size])


# PHONE_COUNTRY_CODES = {
#     '+7': u'Российская Федерация',
# }
# PHONE_COUNTRY_CODES_CHOICES = [(k, u'%s' % k) for k, v in PHONE_COUNTRY_CODES.iteritems()]
#
#
# class PhoneNumberWidget(forms.MultiWidget):
#     def __init__(self, attrs=None):
#         def add_attrs(dest_attrs, new_attrs):
#             dest_attrs = dest_attrs.copy() if dest_attrs else {}
#             for k, v in new_attrs.iteritems():
#                 dest_attrs[k] = ' '.join((dest_attrs[k], v)) if k in dest_attrs else v
#             return dest_attrs
#
#         cc_attrs = add_attrs(attrs, {'class': 'country_code'})
#         pn_attrs = add_attrs(attrs, {'class': 'phone_number', 'maxlength': '20'})
#
#         widgets = (
#             forms.Select(attrs=cc_attrs, choices=PHONE_COUNTRY_CODES_CHOICES),
#             forms.TextInput(attrs=pn_attrs),
#         )
#         super(PhoneNumberWidget, self).__init__(widgets, attrs)
#
#     def decompress(self, value):
#         if value:
#             return value[:2], value[2:]
#         return None, None
#
#     def value_from_datadict(self, data, files, name):
#         value = [u'', u'']
#         # look for keys like name_1, get the index from the end
#         # and make a new list for the string replacement values
#         for d in filter(lambda x: x.startswith(name), data):
#             index = int(d[len(name)+1:])
#             value[index] = data[d]
#         if not value[0] or not value[1]:
#             return None
#         return PhoneNumber.format(u'%s%s' % tuple(value))


class UserProfileChangeForm(forms.ModelForm):
    # salutation field added here for legacy purpose
    salutation = forms.CharField(label=u'Имя', required=False)
    birth_date = forms.CharField(label=u'Дата рождения', help_text=u'Дата рождения в формате ISO 8601.', required=False)

    class Meta:
        model = UserProfile
        exclude = ('user',)

    def clean_birth_date(self):
        raw_date = self.cleaned_data['birth_date']
        if not raw_date.strip():
            return None
        result = dateutil.parser.parse(raw_date)
        if timezone.is_naive(result):
            result = timezone.make_aware(result, timezone.get_default_timezone())
        return result

    def clean(self):
        if 'salutation' in self.cleaned_data:
            self.cleaned_data['first_name'] = self.cleaned_data.pop('salutation')
        return self.cleaned_data


class PhoneVerificationForm(forms.Form):
    phone = forms.CharField(max_length=50, label=u'Номер телефона')
    verifier = forms.CharField(max_length=50, label=u'Код подтверждения')

    def clean_phone(self):
        return PhoneNumber.format(self.cleaned_data.get('phone'))


SEX_CHOICES = (
    (0, u'Не указан'),
    (2, u'Мужской'),
    (1, u'Женский'),
)


class UserCreationForm(forms.Form):
    first_name = forms.CharField(label=u'Имя', max_length=30)
    last_name = forms.CharField(label=u'Фамилия', max_length=30)
    birth_date = forms.DateField(label=u'Дата рождения', widget=AdminDateWidget, required=False)
    sex = forms.ChoiceField(label=u'Пол', choices=SEX_CHOICES)
    phone = forms.RegexField(label=u'Номер телефона', max_length=30, min_length=12, regex=r'^\+\d+$')

    def save(self):
        data = self.cleaned_data

        # create user
        user = User()
        user.username = generate_username()
        password = User.objects.make_random_password()
        user.set_password(password)
        user.first_name = data['first_name']
        user.last_name = data['last_name']
        user.save()

        # update user profile
        user.userprofile.birth_date = data['birth_date'] if data['birth_date'] else None
        user.userprofile.sex = data['sex']
        user.userprofile.save()

        # create phone number
        PhoneNumber.objects.create(
            content_object=user.userprofile,
            phone_number=data['phone'],
            is_verified=True,
            is_active=True,
            is_main=True,
        )

        return user


class UserAndRouteCreationForm(forms.Form):
    post_url = forms.URLField(label=u'Ссылка на пост', required=False)
    post_text = forms.CharField(label=u'Текст поста', widget=forms.Textarea, required=False)

    user_first_name = forms.CharField(label=u'Имя', max_length=255)
    user_last_name = forms.CharField(label=u'Фамилия', max_length=255)
    user_sex = forms.ChoiceField(label=u'Пол', choices=SEX_CHOICES)
    user_phone = forms.CharField(label=u'Номер телефона', max_length=50, required=False)
    user_vk_profile_url = forms.CharField(label=u'Ссылка на страницу пользователя', max_length=255, required=False)

    start_place_country = forms.CharField(label=u'Страна', max_length=255, initial=u'Россия')
    start_place_adm_area_level_1 = forms.CharField(label=u'Республика, область, край и т. п.', max_length=255, required=False)
    start_place_locality = forms.CharField(label=u'Населённый пункт', max_length=255)
    start_place_street = forms.CharField(label=u'Улица', max_length=255, required=False)
    start_place_house = forms.CharField(label=u'Дом', max_length=255, required=False)

    finish_place_country = forms.CharField(label=u'Страна', max_length=255, initial=u'Россия')
    finish_place_adm_area_level_1 = forms.CharField(label=u'Республика, область, край и т. п.', max_length=255, required=False)
    finish_place_locality = forms.CharField(label=u'Населённый пункт', max_length=255)
    finish_place_street = forms.CharField(label=u'Улица', max_length=255, required=False)
    finish_place_house = forms.CharField(label=u'Дом', max_length=255, required=False)

    route_role = forms.ChoiceField(label=u'Роль', choices=ROLE_CHOICES)
    route_departure_date_from = forms.DateField(label=u'С (дата)', widget=DateWidget(usel10n=True))
    route_departure_time_from = forms.TimeField(label=u'С (время)', widget=TimeWidget(usel10n=True))
    route_departure_date_to = forms.DateField(label=u'До (дата)', widget=DateWidget(usel10n=True))
    route_departure_time_to = forms.TimeField(label=u'До (время)', widget=TimeWidget(usel10n=True))

    route_timezone = forms.CharField(label=u'Часовой пояс', max_length=6, initial=u'+07:00')
    route_cost = forms.DecimalField(label=u'Стоимость', required=False)
    route_passengers_count = forms.IntegerField(label=u'Количество мест / попутчиков', required=False)
    route_comment = forms.CharField(label=u'Комментарий', required=False)

    def set_coordinates(self):
        data = self.cleaned_data
        result = dict()
        for place_type in ['start', 'finish']:
            address_components = [
                data['%s_place_country' % place_type],
                data['%s_place_adm_area_level_1' % place_type],
                data['%s_place_locality' % place_type],
                data['%s_place_street' % place_type],
                data['%s_place_house' % place_type],
            ]
            start_place_address = u', '.join([item for item in address_components if not item == ''])
            coordinates = get_coordinates_by_address(start_place_address)
            if coordinates:
                self.cleaned_data['%s_place_latitude' % place_type] = coordinates['latitude']
                self.cleaned_data['%s_place_longitude' % place_type] = coordinates['longitude']
                result['%s_place' % place_type] = True
            else:
                result['%s_place' % place_type] = False
        return result

    def is_valid(self):
        if super(UserAndRouteCreationForm, self).is_valid():
            is_coordinates_set = self.set_coordinates()
            error_list = []
            if not is_coordinates_set['start_place']:
                self._errors["__all__"] = error_list.append(u'Не удаётся найти координаты начальной точки.')
            if not is_coordinates_set['finish_place']:
                self._errors["__all__"] = error_list.append(u'Не удаётся найти координаты конечной точки.')
            if self.cleaned_data['user_phone'] and not format_phone(self.cleaned_data['user_phone']):
                self._errors["__all__"] = error_list.append(u'Некорректный номер телефона.')
            if error_list:
                self._errors["__all__"] = ErrorList(error_list)
        return super(UserAndRouteCreationForm, self).is_valid()

    def save(self):
        data = self.cleaned_data

        # get or create user
        user = get_or_create_account(format_phone(data['user_phone']))
        user.first_name = user.userprofile.first_name = data['user_first_name']
        user.last_name = user.userprofile.last_name = data['user_last_name']
        user.userprofile.sex = data['user_sex']
        user.userprofile.save()
        user.save()

        # create app profile (vk)
        if data['user_vk_profile_url']:
            try:
                consumer = Consumer.objects.get(name='vk')
                vk_group = list(VKGroup.objects.all()[:1])[0]
                vk_user_id = data['user_vk_profile_url'].split('/')[-1]
                url = 'https://api.vk.com/method/users.get?user_ids=%s&access_token=%s' % (vk_user_id, vk_group.access_token)
                response = requests.get(url)
                response = response.json()
                app_user_id = response['response'][0]['uid']
                AppProfile.objects.get_or_create(user=user, consumer=consumer, app_user_id=app_user_id)
            except:
                pass

        # create places
        places = list()
        for place_type in ['start', 'finish']:
            name_components = [
                data['%s_place_locality' % place_type],
                data['%s_place_street' % place_type],
                data['%s_place_house' % place_type],
            ]
            place = Place.objects.create(
                user=user,
                name=u', '.join(item for item in name_components if not item == ''),
                latitude=data['%s_place_latitude' % place_type],
                longitude=data['%s_place_longitude' % place_type],
                country=data['%s_place_country' % place_type],
                adm_area_level_1=data['%s_place_adm_area_level_1' % place_type],
                locality=data['%s_place_locality' % place_type],
                street=data['%s_place_street' % place_type],
                house=data['%s_place_house' % place_type],
            )
            places.append(place)

        # create route
        tz = data['route_timezone']
        dd_from = data['route_departure_date_from'].strftime('%Y-%m-%d')
        dt_from = data['route_departure_time_from'].strftime('%H:%M')
        dd_to = data['route_departure_date_to'].strftime('%Y-%m-%d')
        dt_to = data['route_departure_time_to'].strftime('%H:%M')
        departure_time_from = parse_datetime('%s %s%s' % (dd_from, dt_from, tz))
        departure_time_to = parse_datetime('%s %s%s' % (dd_to, dt_to, tz))
        waiting_time_span = departure_time_to - departure_time_from
        route_data = {
            'user': user.id,
            'departure_time': departure_time_from,
            'places': '%s,%s' % (places[0].id, places[1].id),
            'role': data['route_role'],
            'waiting_time_span': int(round(waiting_time_span.total_seconds() / 60)),
            'walking_distance': 200,
            'distance_extension': 1.5,
            'accept_carpool': True,
            'cost': data['route_cost'] or 0.00,
            'passengers_count': data['route_passengers_count'] or (1 if data['route_role'] == 'passenger' else 3),
            'comment': data['route_comment'],
        }
        route_form = RouteForm(route_data)
        if route_form.is_valid():
            return route_form.save()