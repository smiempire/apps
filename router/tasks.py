# -*- coding: utf-8 -*-
from datetime import timedelta
from celery import task
from celery.utils.log import get_task_logger
from django.utils import timezone
from django.db.models import Q
from apps.router import settings
from transmission.settings import ROUTE_EXPIRATION_DATE
from apps.router.models import Route, Match
from libs.utils import acquire_lock, release_lock

logger = get_task_logger(__name__)


@task(ignore_result=True)
def schedule_regular_routes():
    """Create regular routes instances."""
    lock_id = settings.SCHEDULE_REGULAR_ROUTES_LOCK_NAME
    # cache.add fails if the key already exists
    logger.debug('Started at %s.' % timezone.now().isoformat())
    if not acquire_lock(lock_id, settings.SCHEDULE_REGULAR_ROUTES_LOCK_EXPIRE):
        logger.debug('Aborted because of lock.')
        return

    try:
        now = timezone.now()
        rroutes = Route.objects.filter(
            recurrence__dtend__gt=now,
            last_occurrence_time__lt=now,
            user__is_active=True,
            user__userprofile__is_frozen=False,
        ).exclude(
            status='canceled'
        )
        logger.debug('Selected %d rroutes for processing.' % rroutes.count())
        for rroute in rroutes:
            r = rroute.create_regular_instance()
            if r:
                logger.debug('Regular route %d instance created as %d' % (rroute.id, r.id,))
        logger.debug('All regular routes processed.')
    finally:
        release_lock(lock_id)


@task(ignore_result=True)
def change_routes_status():
    """
    Изменяет статус маршрутов.
    """
    # Переводим активные маршруты с departure_time + ROUTE_EXPIRATION_DATE <= now в статус 'canceled'
    now_time = timezone.now()
    route_expiration_date = timedelta(minutes=ROUTE_EXPIRATION_DATE)
    routes = Route.objects.filter(
        departure_time__lte=now_time-route_expiration_date,
        status='active',
    )
    for route in routes:
        if route.departure_time + route_expiration_date <= now_time:
            route.status = 'done'
            route.save()
            # Отменяем матчи "new, new"
            matches = Match.objects.filter(Q(from_route=route) | Q(to_route=route))
            for match in matches:
                if match.status == 'new' and match.to_status == 'new':
                    match.is_canceled = True
                    match.save()
