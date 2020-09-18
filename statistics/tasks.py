# -*- coding: utf-8 -*-
import inspect
import pkgutil
from importlib import import_module
import os
from django.utils import timezone
from celery import task
import apps.statistics.calculators
from apps.statistics.models import Parameter, Value


@task(ignore_result=True)
def update_statistics():
    """
    Updates statistics.
    """
    pkgpath = os.path.dirname(apps.statistics.calculators.__file__)
    for importer, name, ispkg in pkgutil.iter_modules([pkgpath]):
        if ispkg:
            continue
        module = import_module('apps.statistics.calculators.%s' % name)
        for obj_name, obj in inspect.getmembers(module):
            if (not inspect.isclass(obj)
                    or not issubclass(obj, apps.statistics.calculators.BaseCalculator)
                    or obj is apps.statistics.calculators.BaseCalculator):
                continue
            calculator = obj()
            # try to get parameter if exists or create if it doesn't
            param, created = Parameter.objects.get_or_create(key=name)
            # skip disabled parameters
            if not param.enabled:
                continue
            # calculate next update time to determine whether parameter is up to date or not
            next_update = param.recurrence.after(timezone.now())
            # try to get last parameter value
            last_value = None
            if not created:
                values = param.value_set.order_by('-date_created')
                if len(values):
                    # skip parameter if it is already up to date
                    if next_update and not next_update > param.recurrence.after(values[0].date_created):
                        continue
                    last_value = values[0].data

            new_value = Value()
            new_value.parameter = param
            if last_value:
                new_value.data = calculator.calculate(last_value=last_value)
            else:
                new_value.data = calculator.calculate()
            new_value.save()
