# -*- coding: utf-8 -*-
from datetime import datetime
import json
from django import forms
from django.db.models.fields import NOT_PROVIDED
from django.utils import timezone
import time
from apps.matcher.models import MatchRequest
from apps.matcher.models import Match, Place

__docformat__ = 'restructuredtext ru'

class PlaceForm(forms.ModelForm):
    """Deprecated. Will be deleted soon."""
    class Meta:
        model = Place


class MatchForm(forms.ModelForm):
    """Deprecated. Will be deleted soon."""
    class Meta:
        model = Match

    def __init__(self, data=None, files=None, *args, **kwargs):
        """ Grab the default values from the model and add them to the form so it will validate """
        if data:
            for field in self.Meta.model._meta.fields:
                if field.default != NOT_PROVIDED \
                    and field.name not in data:
                    data[field.name] = field.default
                super(MatchForm, self).__init__(data, files, *args, **kwargs)



class MatcherMatchForm(forms.Form):
    driverRequest = forms.CharField(label=u'запрос водителя')
    riderRequest = forms.CharField(label=u'запрос пассажира')
    cost = forms.DecimalField(max_digits=7, decimal_places=2, label=u'цена')
    meetingPlace = forms.CharField(label=u'место встречи')
    dropOffPlace = forms.CharField(label=u'место высадки')
    meetingTime = forms.IntegerField(label=u'время встречи')
    driverDistance = forms.CharField(label=u'длина пути водителя, м')
    riderDistance = forms.CharField(label=u'длина пути пассажира, м')
    routeExtension = forms.CharField(label=u'коэффициент увеличения пути водителя')
    walkingDistance = forms.CharField(label=u'расстояние от пешехода до места встречи, м')
    id = forms.IntegerField(label=u'номер ответа от подборщика')

    def clean_meetingTime(self):
        extension = self.cleaned_data['meetingTime']
        return timezone.make_aware(datetime(*time.gmtime(int(extension))[:6]), timezone.utc)


    def clean_riderDistance(self):
        extension = self.cleaned_data['riderDistance']
        return int(float(extension))


    def clean_driverDistance(self):
        extension = self.cleaned_data['driverDistance']
        return int(float(extension))


    def clean_walkingDistance(self):
        extension = self.cleaned_data['walkingDistance']
        return int(float(extension))


    def clean_routeExtension(self):
        extension = self.cleaned_data['routeExtension']
        return float(extension)


    def clean_meetingPlace(self):
        meeting_place = self.cleaned_data['meetingPlace']
        return json.loads(meeting_place)


    def clean_dropOffPlace(self):
        meeting_place = self.cleaned_data['dropOffPlace']
        return json.loads(meeting_place)


    def clean_driverRequest(self):
        request_id = int(self.cleaned_data['driverRequest'])
        request = None
        try:
            request = MatchRequest.objects.get(request_id=request_id, route__role='driver')
        except MatchRequest.MultipleObjectsReturned:
            raise forms.ValidationError('There are multiple driver match requests.')
        except MatchRequest.DoesNotExist:
            raise forms.ValidationError('Driver match request does not exists.')
        except Exception, e:
            raise forms.ValidationError(e.message)
        return request


    def clean_riderRequest(self):
        request_id = int(self.cleaned_data['riderRequest'])
        request = None
        try:
            request = MatchRequest.objects.get(request_id=request_id, route__role='passenger')
        except MatchRequest.MultipleObjectsReturned:
            raise forms.ValidationError('There are multiple rider match requests.')
        except MatchRequest.DoesNotExist:
            raise forms.ValidationError('Rider match request does not exists.')
        except Exception, e:
            raise forms.ValidationError(e.message)
        return request


class MatcherCmdForm(forms.Form):
    """
    Форма отправки команд в подборщик.
    """
    METHOD_CHOICES = (
        ('POST', 'POST'),
        ('GET', 'GET'),
    )

    command = forms.CharField(label=u'Path')
    method = forms.ChoiceField(choices=METHOD_CHOICES, label=u'Метод')
    data = forms.CharField(widget=forms.Textarea, label=u'Данные')


    def clean_data(self):
        data = self.cleaned_data['data']
        data = data.replace('\r', '')
        data = json.loads(data)
        return data
