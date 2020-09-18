# -*- coding: utf-8 -*-
from datetime import timedelta, date

from django.core.urlresolvers import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.http import HttpResponse
from libs.admin import admin
from django.contrib.auth.models import Group
from django.utils import dateformat
from daterange_filter.filter import DateRangeFilter

from apps.router.models import Place, PlaceLocalization, PopularPlace, Route, PlaceInRoute, GeographicArea, RouteClick, RoutesClicksStat,\
    Tariff, District
from libs.widgets import PolygonSelectorWidget


class RegularRouteListFilter(admin.SimpleListFilter):
    """
    Фильтр маршрутов по регулярности.
    """
    title = u'Регулярность'
    parameter_name = 'recurrence'

    def lookups(self, request, model_admin):
        return (
            ('once-only', u'Разовые'),
            ('regular', u'Регулярные'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'once-only':
            return queryset.filter(recurrence__isnull=True)
        if self.value() == 'regular':
            return queryset.filter(recurrence__isnull=False)


class UserGroupListFilter(admin.SimpleListFilter):
    title = u'группа пользователей'
    parameter_name = u'user group'

    def lookups(self, request, model_admin):
        return (
            ('scania', u'Скания'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'scania':
            group = Group.objects.filter(name='scania')
            group_id = group[0].id if group else 0
            return queryset.filter(user__groups__in=[group_id])
        else:
            return queryset


class RouteAdmin(admin.ModelAdmin):
    model = Route
    list_display = ('id', 'route', 'user_link', 'role', 'departure_time_period',
                    'carpool', 'taxi', 'friends',)
    date_hierarchy = 'date_created'
    list_select_related = True
    ordering = ('-id',)
    readonly_fields = ('user_link', 'regular_route', 'recurrence',)
    raw_id_fields = ('regular_route', 'recurrence', 'start_place', 'finish_place', 'driver_route')
    list_filter = ('accept_carpool', 'accept_taxi', 'search_friends', 'role', 'user__userprofile__sex',
                   RegularRouteListFilter, ('departure_time', DateRangeFilter), UserGroupListFilter)
    search_fields = ['user__username', 'placeinroute__place__name', 'placeinroute__place__address', 'departure_time']
    actions = ['routes_to_txt']
    list_display_links = ()
    exclude = ['user']

    def route(self, obj):
        url = reverse('admin:router_route_change', args=(obj.user.id,))
        places = '<table style="border:0px"><tr>'
        for p in obj.places:
            places += '<td>'
            places += u'<a href="%s" title="%s">%s</a>' % (reverse('admin:router_place_change', args=(p.id,)), p.address, p.name,)
            places += '<ul>'
            places += '<li>lat:&nbsp;%f, lon:&nbsp;%f</li>' % (p.latitude, p.longitude)
            places += '<ul>'
            places += '</td>'
        places += '</tr></table>'
        yandex = u'<a href="http://maps.yandex.ru/?rtext=%f,%f~%f,%f">Просмотреть на карте</a>' % \
                 (obj.places[0].latitude, obj.places[0].longitude, obj.places[-1].latitude, obj.places[-1].longitude)
        return u'<b>%s</b><br/>%s' % (yandex, places,)
    route.allow_tags = True
    route.admin_order_field = 'id'
    route.short_description = u'Маршрут'

    def user_link(self, obj):

        def calculate_age(born):
            today = timezone.now()
            try: # raised when birth date is February 29 and the current year is not a leap year
                birthday = born.replace(year=today.year)
            except ValueError:
                birthday = born.replace(year=today.year, day=born.day-1)
            if birthday > today:
                return today.year - born.year - 1
            else:
                return today.year - born.year

        url = reverse('admin:auth_user_change', args=(obj.user.id,))
        sex = '?' if not obj.user.userprofile.sex else u'ж' if obj.user.userprofile.sex == 1 else u'м'
        b_day = obj.user.userprofile.birth_date
        age = '?' if not b_day else str(calculate_age(b_day))
        p = obj.user.userprofile
        name = ' '.join([x for x in (p.salutation, ) if x]) or '?'
        phone = p.phone or '?'
        return '<a href="%s">%s</a> (%s,&nbsp;%s, %s, %s)' % \
               (url, str(obj.user), sex, age, name, phone)
    user_link.allow_tags = True
    user_link.admin_order_field = 'user'
    user_link.short_description = u'Пользователь'

    def taxi(self, obj):
        return obj.accept_taxi
    taxi.short_description = u'T'
    taxi.boolean = True
    taxi.admin_order_field = 'accept_taxi'

    def carpool(self, obj):
        return obj.accept_carpool
    carpool.short_description = u'C'
    carpool.boolean = True
    carpool.admin_order_field = 'accept_carpool'

    def friends(self, obj):
        return obj.search_friends
    friends.short_description = u'F'
    friends.boolean = True
    friends.admin_order_field = 'search_friends'

    def departure_time_period(self, obj):
        format = '%d.%m.%Y %H:%M'
        start = obj.departure_time.strftime(format)
        end = obj.departure_time + timedelta(minutes=obj.waiting_time_span)
        end = end.strftime(format)
        return u'<nobr>с %s</nobr><br/><nobr>до %s</nobr>' % (start, end,)
    departure_time_period.allow_tags = True
    departure_time_period.admin_order_field = 'departure_time'
    departure_time_period.short_description = u'Время выезда'

    def routes_to_txt(self, request, queryset):
        """
        Export selected routes in text file.
        """
        route_template = u'%(first_place)s - %(last_place)s с %(departure_time)s %(phone)s %(name)s\n'
        selected_routes = request.POST.getlist(admin.ACTION_CHECKBOX_NAME)
        routes = ''

        for selected_route in selected_routes:
            route = Route.objects.get(id=selected_route)
            context = {}
            context['first_place'] = route.places[0].address
            context['last_place'] = route.places[-1].address
            context['departure_time'] = dateformat.format(route.departure_time, 'd E H:i')
            context['phone'] = route.user.userprofile.phone or '?'
            context['name'] = route.user.userprofile.short_name
            routes += route_template % context

        response = HttpResponse(routes, content_type="text/plain")
        response['Content-Disposition'] = 'attachment; filename="routes.txt"'
        return response
    routes_to_txt.short_description = u'Экспорт в текстовый файл'

    def user_link(self, obj):
        change_url = reverse('admin:auth_user_change', args=(obj.user.id,))
        return mark_safe('<a href="%s">%s</a>' % (change_url, obj.user.username))
    user_link.short_description = u'Пользователь'
    user_link.allow_tags = True
admin.site.register(Route, RouteAdmin)


class GeographicAreaAdmin(admin.ModelAdmin):
    readonly_fields = ('area',)

    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name == 'geographic_polygon':
            return db_field.formfield(widget=PolygonSelectorWidget)
        return super(GeographicAreaAdmin, self).formfield_for_dbfield(db_field, **kwargs)
admin.site.register(GeographicArea, GeographicAreaAdmin)


class PlaceAdmin(admin.ModelAdmin):
    search_fields = ['user__id', 'name', 'locality']
    list_filter = ['geographic_area']
admin.site.register(Place, PlaceAdmin)


class PlaceLocalizationAdmin(admin.ModelAdmin):
    pass
admin.site.register(PlaceLocalization, PlaceLocalizationAdmin)


class RouteClickAdmin(admin.ModelAdmin):
    list_display = ('id', 'route_link', 'date')
    list_filter = (('date', DateRangeFilter),)
    raw_id_fields = ('route',)

    def route_link(self, obj):
        change_url = reverse('admin:router_route_change', args=(obj.route.id,))
        return mark_safe('<a href="%s">%s</a>' % (change_url, obj.route.id))
    route_link.short_description = u'Маршрут'
    route_link.allow_tags = True
admin.site.register(RouteClick, RouteClickAdmin)


class RoutesClicksStatAdmin(admin.ModelAdmin):
    list_display = ('id', 'date_month', 'count')
    date_hierarchy = 'date'

    def date_month(self, obj):
        return u'%s-%0*d' % (obj.date.year, 2, obj.date.month)
    date_month.short_description = u'Месяц'
    date_month.admin_order_field = 'date'
admin.site.register(RoutesClicksStat, RoutesClicksStatAdmin)


class TariffAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'is_default', 'weekdays', 'begin_time', 'end_time', 'begin_date', 'end_date', 'priority',)
admin.site.register(Tariff, TariffAdmin)


class DistrictAdmin(admin.ModelAdmin):
    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name == 'geographic_polygon':
            return db_field.formfield(widget=PolygonSelectorWidget)
        return super(DistrictAdmin, self).formfield_for_dbfield(db_field, **kwargs)
admin.site.register(District, DistrictAdmin)


admin.site.register(PopularPlace)
admin.site.register(PlaceInRoute)