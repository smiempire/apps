# -*- coding: utf-8 -*-
from datetime import timedelta
from celery import task
from celery.utils.log import get_task_logger
from django.db.models import Q
from django.utils import timezone
from apps.orders import settings
from apps.orders.models import Order, OrderStatus, OrderStatusChange
from libs.utils import acquire_lock, release_lock

logger = get_task_logger(__name__)

@task(ignore_result=True)
def rotate_orders():
    """
    Rotate orders among organizations on expire.
    """
    lock_id = settings.ORDER_EXPIRATION_TIME

    logger.debug('Started at %s.' % timezone.now().isoformat())
    if not acquire_lock(lock_id, settings.ORDER_EXPIRATION_TIME):
        logger.debug('Aborted because of lock.')
        return

    try:
        time = timezone.now()
        orders = Order.objects.select_related('route').filter(
            # get expired orders
            Q(status__in=OrderStatus.sources(OrderStatus.EXPIRED, False), expiration_date__lte=time)
            # get orders which was not approved by users
            | Q(status__in=OrderStatus.sources(OrderStatus.APPROVED, False), route__departure_time__lte=time)
            | Q(status=OrderStatus.APPROVED)
        )
        logger.debug('Selected %d orders for processing.' % orders.count())
        for order in orders:
            new_order = None
            try:
                if order.status == OrderStatus.APPROVED and order.route.departure_time + timedelta(seconds=settings.ORDER_APPROVED_TIME) <= time:
                    new_status = OrderStatus.FINISHED
                    reason = 'Finished at %s because user doesn\'t finish or reject approved route manually.' \
                             % time.isoformat()
                elif order.route.departure_time <= time:
                    new_status = OrderStatus.REJECTED
                    reason = 'Rejected at %s because user doesn\'t approve processed route by departure time (%s).' \
                             % (time.isoformat(), order.route.departure_time.isoformat())
                else:
                    new_status = OrderStatus.EXPIRED
                    reason = 'Expired at %s because operator doesn\'t process order by expiration time (%s).' \
                             % (time.isoformat(), order.expiration_date.isoformat())
                    new_order = order.rotate(commit=False)
                    if not new_order:
                        # # TODO: add status to Route and set this status here when no more organizations to route to.
                        # order.route.status = INACTIVE
                        pass
                OrderStatusChange.objects.create(order=order, old_status=order.status, status=new_status, user=None,
                                                 description=reason)
                # first set status for old order
                order.set_status(new_status)
                if new_order:
                    new_order.save()
            except Exception, e:
                logger.error(e.message)
        logger.debug('All orders processed in %s.' % (timezone.now() - time))
    finally:
        release_lock(lock_id)
