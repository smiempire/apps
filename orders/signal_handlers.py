# -*- coding: utf-8 -*-
from datetime import timedelta
import logging
from django.db import models, DatabaseError
from django.utils import timezone
from apps.orders.exceptions import OperationError
from apps.organizations.models import Organization
from apps.router.models import Match, Route
from apps.orders.models import Order, OrderStatusChange
from apps.orders.settings import ORDER_EXPIRATION_TIME

logger = logging.getLogger(__name__)


def create_or_delete_order(sender, instance, **kwargs):
    """
    Creates or deletes orders for routes accepting taxi.
    Connect to post_save signal of Route model.
    """
    if not instance.accept_taxi or instance.departure_time < timezone.now():
        return False

    # если маршрут отменён, то удаляем соответствующий ему заказ
    if instance.status == 'canceled':
        Order.objects.filter(route=instance).delete()
        return False
    # если маршрут завершён, то ничего не делаем
    elif instance.status == 'done':
        return False

    # sort organizations by rating and select topmost
    organizations = Organization.objects.filter(type='taxi', status='active').order_by(*['-rating'])
    if not organizations:
        return False

    order = Order()
    order.route = instance
    order_organization = order.choose_organization(organizations)
    if order_organization:
        order.organization = order_organization
        order.expiration_date = timezone.now() + timedelta(seconds=ORDER_EXPIRATION_TIME)
        order.save()
        return order
    else:
        return None
# models.signals.post_save.connect(create_or_delete_order, Route, dispatch_uid='create_order')


MATCH_TO_ORDER_STATUS_MAP = {
    'new': None,
    'accepted': 'approved',
    'rejected': 'rejected',
    'done': 'finished'
}


def sync_order_status(sender, instance, **kwargs):
    """
    Push match status -> order status.
    Connect to post_save signal of Match model.
    :param sender:
    :param instance:
    :param kwargs:
    :return:
    """
    if not isinstance(instance, Match):
        return

    order_status = MATCH_TO_ORDER_STATUS_MAP.get(instance.status)
    if order_status:
        # update order status
        # update_match_status handler triggers but do nothing because match status already equal to order status.
        # Yes current behaviour leads to one overhead database request. Optimization needed.
        try:
            orders = Order.objects.select_for_update(nowait=True).filter(other_match = instance).exclude(status = order_status)
            if orders.exists():
                order = orders[0]
                old_status = order.status

                try:
                    order.set_status(order_status, user=instance.from_route.user)
                    OrderStatusChange.objects.create(order = order, old_status = old_status,
                        status = order.status, user = instance.from_route.user)
                except OperationError, e:
                    logger.error(e.message)
                # if match rejected by user, create new order for next organization
                if instance.status == 'rejected':
                    order.rotate()
        except DatabaseError, e:
            logger.error(e.message)
# models.signals.post_save.connect(sync_order_status, Match, dispatch_uid='update_order_status')


ORDER_TO_MATCH_STATUS_MAP = {
    'new' : None,
    'accepted' : None,
    'processed' : 'accepted',
    'approved' : None,
    'finished' : None,
    'rejected' : 'rejected',
    'expired' : None,
}


def sync_match_status(sender, instance, **kwargs):
    """
    Push order status -> match status.
    Connect to post_save signal of Order model.
    :param sender:
    :param instance:
    :param kwargs:
    :return:
    """
    if not isinstance(instance, Order):
        return

    match_status = ORDER_TO_MATCH_STATUS_MAP.get(instance.status)
    if match_status:
        # update match status
        # update_order_status handler triggers but do nothing because order status already equal to match status.
        # Yes current behaviour leads to one overhead database request. Optimization needed.
        matches = Match.objects.filter(id=instance.match_id).exclude(status = match_status)
        if matches.exists():
            match = matches.latest('id')
            match.status = match_status
            match.save()
# models.signals.post_save.connect(sync_match_status, Order, dispatch_uid='update_order_status')
