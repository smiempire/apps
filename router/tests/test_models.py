# coding: utf-8
from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from piston.resource import Resource
from json import loads
from django.utils import timezone
from mock import Mock

import api_v1.handlers.router as RH
from api_v1.urls import auth
from apps.router.models import Place, PlaceLocalization


class PlaceLocalizationTestCase(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username='asdka22asd',
                                             email='a@a.ru',
                                             password='pussword')

    def test_create(self):
        resp = Mock(status_code=200,
                    json=Mock(return_value=loads(open('apps/router/tests/yan'
                                                      'dextest.json').read())))
        RH.requests.post = Mock(return_value=resp)
        places_handler = Resource(RH.PlacesHandler, authentication=auth)
        postdata = {'name': "Hasana Tufana, 14",
                    'latitude': 55.741906,
                    'longitude': 52.41375,
                    'postal_code': "453365",
                    'country': "Russia",
                    'adm_area_level_1': "Respublika Tatarstan",
                    'adm_area_level_2': "gorodskoy okrug Naberezhnye Chelny",
                    'locality': "Naberezhnye Chelny",
                    'street': "Hasana Tufana",
                    'house': u"14"}
        incdata = {u'name': u"Hasana Tufana, 14",
                   u'latitude': 55.741906,
                   u'longitude': 52.41375,
                   u'postal_code': u"453365",
                   u'country': u"Россия",
                   u'adm_area_level_1': u"Республика Татарстан",
                   u'adm_area_level_2': u"городской округ Набережные Челны",
                   u'locality': u"Набережные Челны",
                   u'street': u"проспект Хасана Туфана",
                   u'house': u"14",
                   u'porch': u"",
                   u'district_id': u"",
                   u'address': u"453365, Россия, Республика Татарстан, "
                               u"Набережные Челны, проспект Хасана Туфана, 14"}
        request = self.factory.post('/1/places.json?app_localization=en',
                                    data=postdata)
        request.user = self.user
        resp = places_handler(request)
        self.assertEqual(resp.status_code, 200)
        json = loads(resp.content)
        # Test reponse
        self.assertIn(u'last_ride', json)
        for i in postdata:
            self.assertEqual(json[i], postdata[i])
        # Now test the same in DB (Place)
        if incdata[u'district_id'] == u"":
            del incdata[u'district_id']
        del postdata['name']
        del postdata['longitude']
        del postdata['latitude']
        del postdata['postal_code']
        place = Place.objects.filter(**incdata).order_by('-last_ride')
        self.assertGreater(len(place), 0)
        # self.assertEqual(place[0].last_ride, json[u'last_ride'])
        # ... and PlaceLocalization
        place_loc = PlaceLocalization.objects.filter(**{unicode(k): unicode(v)
                                                     for k, v in
                                                     postdata.iteritems()})
        self.assertGreater(len(place), 0)
