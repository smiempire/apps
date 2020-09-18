# -*- coding: utf-8 -*-

from libs.admin import admin
from apps.organizations.models import Organization
from libs.widgets import PolygonSelectorWidget


class OrganizationAdmin(admin.ModelAdmin):

    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name == 'geographic_polygon':
            return db_field.formfield(widget=PolygonSelectorWidget)
        return super(OrganizationAdmin, self).formfield_for_dbfield(db_field, **kwargs)


admin.site.register(Organization, OrganizationAdmin)