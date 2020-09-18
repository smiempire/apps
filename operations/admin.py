# -*- coding: utf-8 -*-

from libs.admin import admin

from apps.operations.models import Operation


class OperationAdmin(admin.ModelAdmin):
    list_display = ('id', 'operation_key', 'key', 'status', 'client', 'data', 'date_created', 'date_modified')
    search_fields = ('key', '_data')
    list_filter = ('status', 'client', 'operation_key')

    def data(self, obj):
        result = []
        verifiers = ', '.join(obj.data.get('verifiers', ''))
        if verifiers:
            result.append('verifiers: ' + verifiers)
        client_data = obj.data.get('client_data')
        if client_data:
            result.append('client data: ' + client_data)
        return '<br>'.join(result)
    data.allow_tags = True

admin.site.register(Operation, OperationAdmin)