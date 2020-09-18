# -*- coding: utf-8 -*-

from apps.statistics.models import Parameter, Value
from libs.admin import admin

admin.site.register(Parameter)
admin.site.register(Value)
