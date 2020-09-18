# -*- coding: utf-8 -*-
import logging

from django.db.models.signals import post_save
from celery import chain

from apps.router.models import Route
from apps.matcher.models import prepare_route_data
from apps.matcher.stub_tasks import create, update, delete
from apps.matcher.tasks import save_matches, update_matches

logger = logging.getLogger(__name__)


def matcher_management(sender, instance, **kwargs):
    """
    Добавляет, удаляет, изменяет маршрут в подборщике.
    Обращение к подборщику осуществляется посредством вызова celery-задачи подборщика.
    После выполнения задачи create её результат передаётся в аргумент celery-задачи API save_matches.
    Аналогично с update.
    """
    if sender != Route:
        return

    if not instance.send_to_matcher:
        return

    # если маршрут отменён, то удаляем маршрут из матчера
    if instance.status == 'canceled':
        delete.delay(instance.id)
        return

    route_data = prepare_route_data(instance)

    if route_data:
        # если создан новый маршрут, то создаём его в матчере и сохраняем матчи
        if kwargs['created']:
            chain(create.s(route_data), save_matches.s()).apply_async()
        # если маршрут обновлён, то обновляем его в матчере и обновляем матчи
        else:
            chain(update.s(route_data), update_matches.s(instance.id)).apply_async()


post_save.connect(matcher_management, sender=Route, weak=False, dispatch_uid='send_route_to_matcher')
