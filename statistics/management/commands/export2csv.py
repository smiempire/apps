# -*- coding: utf-8 -*-
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils.encoding import smart_str
import re
from relationships.models import Relationship
from apps.matcher.models import Match
from apps.router.models import Route, PlaceInRoute, Place

class Command(BaseCommand):
    help = 'Exports data to csv files for further analysis.'

    def _write(self, filename, *records):
        with open(filename, 'w') as f:
            for rec in records:
                s = '%s\n' % ';'.join(map(lambda s: re.sub(r'[\n;]', ' ', s), map(str.strip, map(smart_str, rec))))
                f.write(s)

    def _export(self, model, *fields, **kwargs):
        name = model.__name__.lower()
        print 'Exporting %s...' % name
        records = [fields]
        records.extend(model.objects.filter(**kwargs).values_list(*fields))
        self._write('%s.csv' % name, *records)
        print 'Done.'

    def handle(self, *args, **options):
        fields = (
            'id', 'username', 'first_name', 'last_name', 'email', 'last_login', 'date_joined',
            'userprofile__salutation', 'userprofile__phone', 'userprofile__birth_date', 'userprofile__sex',
        )
        self._export(User, *fields)

        fields = (
            'id', 'user_id', 'role', 'departure_time', 'waiting_time_span', 'passengers_count', 'cost',
            'walking_distance', 'distance_extension', 'match_waiting_time', 'date_created', 'date_modified',
            'regular_route_id', 'recurrence__recurrence',
            'accept_carpool', 'accept_taxi', 'accept_bus', 'search_friends',
        )
        self._export(Route, *fields)

        fields = (
            'id', 'user_id', 'name', 'address', 'last_ride',
        )
        self._export(Place, *fields)

        fields = (
            'route_id', 'index', 'place_id',
        )
        self._export(PlaceInRoute, *fields)

        fields = (
            'match_request__route_id', 'matched_request__route_id', 'meeting__time', 'distance', 'distance_extension',
        )
        self._export(Match, *fields)

        fields = (
            'from_user_id', 'to_user_id', 'status__from_slug', 'created',
        )
        self._export(Relationship, *fields)
