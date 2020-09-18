# -*- coding: utf-8 -*-
from django.forms import widgets
from django.utils.safestring import mark_safe


class PolygonSelectorWidget(widgets.HiddenInput):
    class Media:
        css = {
            'all': ('mapWidget.css',),
        }
        js = (
            'http://openlayers.org/api/OpenLayers.js',
            'imagePolygonSelector.js',
            'mapWidget.js',
        )

    def render(self, name, value, attrs=None, choices=()):
        substitutions = dict()
        substitutions['input'] = super(PolygonSelectorWidget, self).render(name, value, attrs)
        substitutions['id'] = name
        return mark_safe(self.template % substitutions)

    template = u'''
<div>%(input)s</div><div id="%(id)s" class="map"></div>'''
