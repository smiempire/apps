# -*- coding: utf-8 -*-
from datetime import timedelta
from django import forms
from django.db.models.fields import NOT_PROVIDED
from django.dispatch import Signal
from django.utils import timezone
from recurrence.base import deserialize
from recurrence.exceptions import DeserializationError
from apps.router.models import Place, Route, Recurrence, Appointment, Match
import dateutil.parser

__docformat__ = 'restructuredtext ru'


class PlaceForm(forms.ModelForm):
    class Meta:
        model = Place

route_created = Signal(providing_args=["route", "user_agent"])


class RouteForm(forms.ModelForm):
    # Костыль. Убрать после перехода всех на 1.1.5b
    user_agent = "ru.ktovputi.android-v1.1.5b"

    departure_time = forms.CharField(label=u'Время выезда', help_text=u'Время выезда в формате ISO 8601.')
    places = forms.CharField(min_length=3, label=u'Места', help_text=u'Список мест в маршруте.')
    recurrence = forms.CharField(required=False, label=u'Правило повторения маршрута', help_text=u'Правило повторения маршрута в формате RFC2445.')

    class Meta:
        model = Route

    def __init__(self, data=None, files=None, *args, **kwargs):
        """ Grab the default values from the model and add them to the form so it will validate """
        if data:
            for field in self.Meta.model._meta.fields:
                if field.default != NOT_PROVIDED\
                and field.name not in data:
                    data[field.name] = field.default
        super(RouteForm, self).__init__(data, files, *args, **kwargs)

    def clean_departure_time(self):
        raw_date = self.cleaned_data['departure_time']
        result = dateutil.parser.parse(raw_date)
        if timezone.is_naive(result):
            result = timezone.make_aware(result, timezone.get_default_timezone())
        return result

    def clean_places(self):
        places = []
        places_ids = self.cleaned_data['places']
        places_ids = places_ids.split(',')
        for place_id in places_ids:
            try:
                place = Place.objects.get(pk=place_id)
            except Place.DoesNotExist:
                raise forms.ValidationError(u'Place %s doesn\'t exists.' % place_id)
            except Place.MultipleObjectsReturned:
                raise forms.ValidationError(u'There are fiew places with Id %s.' % place_id)
            places += [place]
        return places

    def clean_recurrence(self):
        r = self.cleaned_data['recurrence']

        if not r:
            return None

        try:
            # при создании маршрута recurrence приходит сюда в виде строки
            r = deserialize(r)
        except DeserializationError:
            # при изменении маршрута приходит id уже существующего recurrence
            r = Recurrence.objects.get(id=r)
            r = r.recurrence

        if self.instance and self.instance.recurrence_id:
            new_dt = self.cleaned_data.get('departure_time')
            old_r = self.instance.recurrence.recurrence
            old_r.dtstart = old_r.dtstart.replace(
                hour=new_dt.hour,
                minute=new_dt.minute,
                second=new_dt.second,
            )
            old_r.dtend = old_r.dtend.replace(
                hour=new_dt.hour,
                minute=new_dt.minute,
                second=new_dt.second,
            )
            r.dtstart = old_r.dtstart
            r.dtend = old_r.dtend
        else:
            dtstart = self.cleaned_data.get('departure_time')
            r.dtstart = dtstart
            r.dtend = dtstart + timedelta(days=365*100)

        recur = Recurrence()
        recur.recurrence = r
        recur.dtstart = r.dtstart
        recur.dtend = r.dtend
        recur.save()
        return recur

    def save(self, commit=True):
        places = self.cleaned_data.pop('places')
        inst = super(RouteForm, self).save(commit=False)
        inst.places = places
        if commit:
            inst.save()
        return inst


class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment


    def __init__(self, data=None, files=None, *args, **kwargs):
        """ Grab the default values from the model and add them to the form so it will validate """
        if data:
            for field in self.Meta.model._meta.fields:
                if field.default != NOT_PROVIDED\
                and field.name not in data:
                    data[field.name] = field.default
                super(AppointmentForm, self).__init__(data, files, *args, **kwargs)



class MatchForm(forms.ModelForm):
    class Meta:
        model = Match


    def __init__(self, data=None, files=None, *args, **kwargs):
        """ Grab the default values from the model and add them to the form so it will validate """
        if data:
            for field in self.Meta.model._meta.fields:
                if field.default != NOT_PROVIDED\
                and field.name not in data:
                    data[field.name] = field.default
                super(MatchForm, self).__init__(data, files, *args, **kwargs)
