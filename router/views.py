# -*- coding: utf-8 -*-
import urllib2
from datetime import timedelta

from django.views.generic import TemplateView
from django.utils.dateformat import format
from django.utils import timezone
from django.views.generic.base import RedirectView
from django.conf import settings

from apps.router.models import Route, RoutesClicksStat


def get_city_image(locality):
    cities = {
        u'казань': 'kazan',
        u'краснодар': 'krasnodar',
        u'красноярск': 'krasnoyarsk',
        u'москва': 'moscow',
        u'нижний новгород': 'nnovgorod',
        u'омск': 'omsk',
        u'оренбург': 'orenburg',
        u'пенза': 'penza',
        u'ростов-на-дону': 'rostov',
        u'рязань': 'ryazan',
        u'санкт-петербург': 'saint-p',
        u'уфа': 'ufa',
        u'челябинск': 'chelyabinsk',
        u'ярославль': 'yaroslavl',
    }
    image_path = 'assets/cities/'
    image = 'default'
    locality = locality.lower()
    for city in cities:
        if city in locality:
            image = cities[city]
            break
    image = image_path + image + '.jpg'
    return image


class RoutesWidgetView(TemplateView):
    template_name = 'routes_widget.html'

    def get_context_data(self, **kwargs):
        time_start = timezone.now()
        time_end = time_start + timedelta(days=14)
        routes = Route.objects.filter(
            departure_time__gt=time_start,
            departure_time__lt=time_end,
            is_intercity=True,
        ).order_by('?')[0:30]

        result = []

        for route in routes:
            if not route.places[0].locality or not route.places[-1].locality:
                continue

            url_context = {
                'sp_lat': route.places[0].latitude,
                'sp_lon': route.places[0].longitude,
                'fp_lat': route.places[-1].latitude,
                'fp_lon': route.places[-1].longitude,
                'dt': format(route.departure_time, 'c'),
                'wts': route.waiting_time_span,
                'role': 'driver' if route.role == 'passenger' else 'passenger',  # роль ставим противоположную данному маршруту
                'rid': route.id,
            }
            hash_str = 'sp=%(sp_lat)s,%(sp_lon)s&fp=%(fp_lat)s,%(fp_lon)s&dt=%(dt)s&wts=%(wts)s&rl=%(role)s&rid=%(rid)s'
            url = 'https://web.ktovputi.ru#' + urllib2.quote(hash_str % url_context)

            data = {
                'url': url,
                'image': get_city_image(route.places[0].locality),
                'date': format(route.departure_time, 'd E'),
                'role': u'водитель' if route.role == 'driver' else u'пассажир',
                'start': route.places[0].get_clean_locality(),
                'finish': route.places[-1].get_clean_locality(),
            }
            result.append(data)

        return {'routes': result}


class RouteRedirectView(RedirectView):
    permanent = False
    query_string = True

    def get_redirect_url(self, *args, **kwargs):
        # ищем маршрут и сохраняем клик
        route = Route.objects.filter(char_id=kwargs['char_id'])
        if route:
            RoutesClicksStat.objects.add_click()

        # если к нам зашел петушок с мобилкой, то шлем его в стор
        agent = self.request.META['HTTP_USER_AGENT'].lower()
        if 'android' in agent:
            return 'https://play.google.com/store/apps/details?id=ru.ktovputi.android&hl=ru'
        elif 'ios' in agent:
            return 'https://itunes.apple.com/ru/app/vputi/id733142744?l=ru&ls=1&mt=8'

        # если зашел господин с браузером, то определяем, куда его направить дальше: в vk-app или в web-app
        vk = True if self.request.META['HTTP_HOST'] == settings.SHORT_DOMAIN_VK else False
        base_app_url = 'https://vk.com/app2370553_101413049' if vk else 'http://www.ktovputi.ru/webapp/'

        # отдаем браузерогосподину положенную ему ссылку
        return route[0].get_webapp_link(vk=vk) if route else base_app_url
