# -*- coding: utf-8 -*-
import json
import logging
from piston.utils import rc
from libs.piston_extensions.handlers import CollectionBaseHandler
from apps.matcher.forms import MatcherMatchForm
from apps.router.forms import AppointmentForm, MatchForm

__docformat__ = 'restructuredtext ru'

logger = logging.getLogger(__name__)

class MatcherHandler(CollectionBaseHandler):
    """Ресурс обеспечивающий приём сообщений о подборе попутчика от подборщика."""

    exclude = ()
    allowed_methods = ('POST',)


    def create(self, request, *args, **kwargs):
        match = request.POST.get('json', None)

        if not match:
            return rc.BAD_REQUEST

        print match

        match = json.loads(match)
        match['meetingPlace'] = json.dumps(match['meetingPlace'])
        match['dropOffPlace'] = json.dumps(match['dropOffPlace'])

        match_report_form = MatcherMatchForm(match)

        is_valid = match_report_form.is_valid()

        if not is_valid:
            # TODO: Write error message to log.
            logger.error(str(match_report_form.errors))
            print match_report_form.errors
            return {"resultCode" : 0}

        driver_request = match_report_form.cleaned_data['driverRequest']
        driver_distance = match_report_form.cleaned_data['driverDistance']
        driver_distance_extension = int(match_report_form.cleaned_data['driverDistance'] * match_report_form.cleaned_data['routeExtension'])

        passenger_request = match_report_form.cleaned_data['riderRequest']
        passenger_distance = match_report_form.cleaned_data['riderDistance']
        passenger_distance_extension = match_report_form.cleaned_data['walkingDistance']

        cost = match_report_form.cleaned_data['cost']

        # Сохраняем встречу.
        meeting_place = match_report_form.cleaned_data['meetingPlace']
        meeting = {
            'lat' : meeting_place['lat'],
            'lon' : meeting_place['lon'],
            'address' : meeting_place.get('name', ''),
            'time' : match_report_form.cleaned_data['meetingTime'],
            }
        meeting_form = AppointmentForm(meeting)
        if not meeting_form.is_valid():
            return rc.BAD_REQUEST
        meeting = meeting_form.save()

        # Сохраняем высадку.
        dropoff_place = match_report_form.cleaned_data['dropOffPlace']
        dropoff = {
            'lat' : dropoff_place['lat'],
            'lon' : dropoff_place['lon'],
            'address' : dropoff_place.get('name', ''),
            }
        dropoff_form = AppointmentForm(dropoff)
        if not dropoff_form.is_valid():
            return rc.BAD_REQUEST
        dropoff = dropoff_form.save()

        # Сохраняем соответствие для водителя.
        driver_match = {
            'from_route' : driver_request.route_id,
            'to_route' : passenger_request.route_id,
            'meeting' : meeting.id,
            'dropoff' : dropoff.id,
            'cost' : cost,
            'distance' : driver_distance,
            'distance_extension' : driver_distance_extension,
            'status' : 'accepted',
            }
        match_form = MatchForm(driver_match)
        if not match_form.is_valid():
            return rc.BAD_REQUEST
        driver_match = match_form.save()

        # Сохраняем соответствие для пассажира.
        passenger_match = {
            'from_route' : passenger_request.route_id,
            'to_route' : driver_request.route_id,
            'meeting' : meeting.id,
            'dropoff' : dropoff.id,
            'cost' : cost,
            'distance' : passenger_distance,
            'distance_extension' : passenger_distance_extension,
            'status' : 'accepted',
            }
        match_form = MatchForm(passenger_match)
        if not match_form.is_valid():
            return rc.BAD_REQUEST
        passenger_match = match_form.save()

        return  {"resultCode" : 0}
