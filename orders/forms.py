# -*- coding: utf-8 -*-
import dateutil.parser
from django import forms
from django.contrib.auth.models import User
from django.utils import timezone

class SetOrderStatusForm(forms.Form):
    user = forms.ModelChoiceField(User.objects.all(), required=False,
        label=u'Оператор', help_text=u'Обязательно при принятии заявки.')
    cost = forms.DecimalField(max_digits=11, decimal_places=2, required=False, label=u'Цена')
    time = forms.CharField(required=False,
        label=u'Время прибытия машины', help_text=u'Дата и время указываются в формате ISO 8601.')

    def clean_time(self):
        raw_date = self.cleaned_data['time']
        result = dateutil.parser.parse(raw_date)
        if timezone.is_naive(result):
            result = timezone.make_aware(result, timezone.get_default_timezone())
        result.replace(microsecond=0)
        return result
