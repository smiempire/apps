# -*- coding: utf-8 -*-
from apps.matcher.tasks import save_matches


def match_routes(driver_route_id, passenger_route_id, driver_status='new', passenger_status='new'):
    """
    Искусственно подбирает друг другу переданные маршруты.
    """
    match = {
        'driver': driver_route_id,
        'rider': passenger_route_id,
        'grade': 1,
        'detour': 0,
        'driver_status': driver_status,
        'rider_status': passenger_status,
    }
    save_matches([match])
