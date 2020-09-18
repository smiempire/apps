# -*- coding: utf-8 -*-
import json
from django.contrib.auth.models import User
from django.test.testcases import TestCase
import time
from ..apps.matcher.models import MatchRequest
from apps.router.models import Route
from router.tests.places import POST_AUTH_PARAMS
from router.tests.routes import POST_ROUTE_DRIVER_PARAMS, POST_ROUTE_PASSENGER_PARAMS

__docformat__ = 'restructuredtext ru'


class MatchesTests(TestCase):

    fixtures = ['test_data.json']

    def setUp(self):
        self.user = User.objects.get(pk=2)
        self.client.post('/1/session.json', POST_AUTH_PARAMS)


    def test_match_request_creation_on_new_route(self):
        resp = self.client.post('/1/routes.json', POST_ROUTE_DRIVER_PARAMS)
        self.assertEquals(resp.status_code, 200)
        route_dict = json.loads(resp.content)
        routes = Route.objects.filter(pk=route_dict['id'])
        self.assertEquals(len(routes), 1)
        route = routes[0]
        time.sleep(15)
        self.assertGreater(len(MatchRequest.objects.filter(route=route)), 0)


class MatchesGetTests(TestCase):

    fixtures = ['test_data.json']

    def setUp(self):

        self.user = User.objects.get(pk=2)
        self.client.post('/1/session.json', POST_AUTH_PARAMS)


    def test_get_route_matches_by_user(self):
        resp = self.client.post('/1/routes.json', POST_ROUTE_DRIVER_PARAMS)
        self.assertEquals(resp.status_code, 200)
        route_dict = json.loads(resp.content)
        self.assertEquals(len(Route.objects.filter(pk=route_dict['id'])), 1)
        driver_route = Route.objects.get(pk=route_dict['id'])
        driver_mr = driver_route.matchrequest

        resp = self.client.post('/1/routes.json', POST_ROUTE_PASSENGER_PARAMS)
        self.assertEquals(resp.status_code, 200)
        route_dict = json.loads(resp.content)
        self.assertEquals(len(Route.objects.filter(pk=route_dict['id'])), 1)
        passenger_route = Route.objects.get(pk=route_dict['id'])
        passenger_mr = passenger_route.matchrequest

        # waiting matcher response
        time.sleep(30)

        route = driver_route
        resp = self.client.get('/1/routes/%d/matches.json' % route.id)
        print resp.content
        self.assertEquals(resp.status_code, 200)
        match_dict = json.loads(resp.content)
        self.assertEquals(len(route.matchrequest.matched_set.all()), len(match_dict))