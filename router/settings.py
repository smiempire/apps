# -*- coding: utf-8 -*-
from django.conf import settings

# Normally lock released every time process success,
# but if something went wrong lock will be auto released after SCHEDULE_REGULAR_ROUTES_LOCK_EXPIRE seconds.
DEFAULT_SCHEDULE_REGULAR_ROUTES_LOCK_EXPIRE = 60*60
SCHEDULE_REGULAR_ROUTES_LOCK_EXPIRE = getattr(settings, 'SCHEDULE_REGULAR_ROUTES_LOCK_EXPIRE',
                                              DEFAULT_SCHEDULE_REGULAR_ROUTES_LOCK_EXPIRE)

DEFAULT_SCHEDULE_REGULAR_ROUTES_LOCK_NAME = 'router.schedule_regular_routes'
SCHEDULE_REGULAR_ROUTES_LOCK_NAME = getattr(settings, 'SCHEDULE_REGULAR_ROUTES_LOCK_NAME',
                                            DEFAULT_SCHEDULE_REGULAR_ROUTES_LOCK_NAME)
