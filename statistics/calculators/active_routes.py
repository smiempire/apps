# -*- coding: utf-8 -*-
from django.utils import timezone
from apps.router.models import Route
from apps.statistics.calculators import BaseCalculator


class ActiveRoutesCalculator(BaseCalculator):

    def calculate(self, *args, **kwargs):
        return Route.objects.filter(departure_time__gte=timezone.now()).exclude(status='canceled').count()
