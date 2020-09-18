# -*- coding: utf-8 -*-

from libs.admin import admin
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe

from apps.devices.models import AndroidDevice, IosDevice, WindowsPhoneDevice


class IosDeviceAdmin(admin.ModelAdmin):
    model = IosDevice
    readonly_fields = ('device_link',)

    def device_link(self, obj):
        change_url = reverse('admin:iospush_device_change', args=(obj.device.id,))
        return mark_safe('<a href="%s">%s</a>' % (change_url, obj.device.id))
    device_link.short_description = u'Устройство'
    device_link.allow_tags = True


admin.site.register(AndroidDevice)
admin.site.register(WindowsPhoneDevice)
admin.site.register(IosDevice, IosDeviceAdmin)
