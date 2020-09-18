# -*- coding: utf-8 -*-

from libs.admin import admin
from apps.logs import models


class LogAdmin(admin.ModelAdmin):
    model = models.Log
    list_display = ('id', 'time', 'type', 'key', 'text',)
    list_filter = ('type', 'key',)
admin.site.register(models.Log, LogAdmin)
