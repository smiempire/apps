# -*- coding: utf-8 -*-
from django.contrib import admin

from apps.consumers.models import ConsumerVersions, ConsumerGeographicArea


class ConsumerVersionsAdmin(admin.ModelAdmin):
    list_display = ('id', 'consumer', 'platform', 'soft_major', 'soft_minor', 'soft_patch', 'hard_major', 'hard_minor',
                    'hard_patch',)
admin.site.register(ConsumerVersions, ConsumerVersionsAdmin)


class ConsumerGeographicAreaAdmin(admin.ModelAdmin):
    list_display = ('id', 'consumer', 'geographic_area',)
admin.site.register(ConsumerGeographicArea, ConsumerGeographicAreaAdmin)
