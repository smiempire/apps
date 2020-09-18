# -*- coding: utf-8 -*-
from datetime import timedelta
import logging
from django.contrib.auth.models import User
from django.db import models, DatabaseError
from django.utils import timezone
from apps.orders.settings import ORDER_EXPIRATION_TIME
from apps.organizations.models import Organization
from apps.router.models import Route, Match, Appointment
from apps.orders.exceptions import OperationError

logger = logging.getLogger(__name__)

ORDER_STATUS_CHOICES = (
    ('new', u'Новый'),
    ('accepted', u'Принят оператором'),
    ('processed', u'Обработан оператором'),
    ('approved', u'Принят клиентом'),
    ('rejected', u'Отклонён'),
    ('expired', u'Просрочен'),
    ('finished', u'Закрыт'),
)


class OrderStatus(object):
    NEW = 'new' # новый
    ACCEPTED = 'accepted'   # принят оператором
    PROCESSED = 'processed' # обработан оператором
    APPROVED = 'approved'   # подтверждён пользователем
    FINISHED = 'finished'   # пользователь подтвердил выполнение заказа
    REJECTED = 'rejected'   # отклонён
    EXPIRED = 'expired'     # просрочен

    ORDER_STATUS_WORKFLOW = {
        NEW: (NEW, ACCEPTED, REJECTED, EXPIRED,),
        ACCEPTED: (ACCEPTED, PROCESSED, REJECTED, EXPIRED,),
        PROCESSED: (PROCESSED, APPROVED, REJECTED,),
        APPROVED: (APPROVED, FINISHED, REJECTED,),
        FINISHED: (FINISHED, REJECTED,),
        REJECTED: (REJECTED,),
        EXPIRED: (EXPIRED,),
    }

    @classmethod
    def transition_valid(cls, old, new):
        return new in cls.ORDER_STATUS_WORKFLOW[old]

    @classmethod
    def sources(cls, status, self_include=True):
        if self_include:
            return tuple([k for k, v in cls.ORDER_STATUS_WORKFLOW.iteritems() if status in v])
        else:
            return tuple([k for k, v in cls.ORDER_STATUS_WORKFLOW.iteritems() if k != status and status in v])

    @classmethod
    def targets(cls, status):
        return cls.ORDER_STATUS_WORKFLOW[status]


class OrderStatusChange(models.Model):
    order = models.ForeignKey('Order')
    old_status = models.CharField(u'статус подбора', choices=ORDER_STATUS_CHOICES, max_length=9, default='new', blank=True)
    status = models.CharField(u'статус подбора', choices=ORDER_STATUS_CHOICES, max_length=9, default='new', blank=True)
    user = models.ForeignKey(User, blank=True, null=True)
    description = models.CharField(u'причина смены статуса', max_length=255, blank=True)
    modified_date = models.DateTimeField(u'дата изменения', blank=True)
    created_date = models.DateTimeField(u'дата создания', blank=True)

    def save(self, *args, **kwargs):
        self.modified_date = timezone.now()
        if not self.created_date:
            self.created_date = self.modified_date
        super(OrderStatusChange, self).save(*args, **kwargs)


class Order(models.Model):
    """
    Order for taxi. WARNING: Use appropriate methods to change order status.

    Each route can have multiple orders.
    Each new order gets expiration_date and has blank operator.
    When expiration_date comes, we create new order for route but for another organization
    with new expiration_date and set expired status for self.
    Operator field gets value when operators app accepts order.
    If operator process order and propose car for order then match and other_match gets value.
    Else if operator can't propose car he must reject order.
    """
    route = models.ForeignKey(Route, related_name='orders')
    organization = models.ForeignKey(Organization, related_name='orders')
    expiration_date = models.DateTimeField(u'время жизни заказа', blank=True, null=True)
    operator = models.ForeignKey(User, related_name='orders', blank=True, null=True)
    match = models.OneToOneField(Match, related_name='order', blank=True, null=True)
    other_match = models.OneToOneField(Match, related_name='other_order', blank=True, null=True)
    status = models.CharField(u'статус заказа', choices=ORDER_STATUS_CHOICES, max_length=9, default='new', blank=True)
    modified_date = models.DateTimeField(u'дата изменения', blank=True)
    created_date = models.DateTimeField(u'дата создания', blank=True)

    def refresh(self):
        updated = Order.objects.filter(id=self.id)[0]
        fields = [f.name for f in self._meta._fields()
                  if f.name != 'id']
        for field in fields:
            setattr(self, field, getattr(updated, field))

    def check_status_transition(self, new_status):
        if not OrderStatus.transition_valid(self.status, new_status):
            raise OperationError('Change status from ''%s'' to ''%s'' is prohibited.' % (self.status, new_status))

    def accept(self, user, **kwargs):
        """
        Accept order.
        :exception OperationError: Raise if something go wrong during accept.
        :param user: Accepting operator.
        :return: Nothing
        """
        if self.expiration_date <= timezone.now():
            raise OperationError('Order is expired.')

        if self.status == OrderStatus.ACCEPTED or self.status not in OrderStatus.sources(OrderStatus.ACCEPTED):
            raise OperationError('Order is already accepted by another operator.')

        # try to accept order
        try:
            # get unaccepted order, lock it and update
            count = Order.objects.select_for_update(nowait=True)\
                    .filter(id=self.id, status__in=OrderStatus.sources(OrderStatus.ACCEPTED))\
                    .update(status=OrderStatus.ACCEPTED, operator=user, modified_date=timezone.now())
            if not count:
                raise OperationError('Order already accepted or doesn\'t exists.')
            else:
                # update model fields on success
                self.refresh()
        except DatabaseError, e:
            raise OperationError('Order is already accepted by another operator.')

    def process(self, time=None, cost=None, **kwargs):
        """
        Process order.
        :exception OperationError: Raise if something go wrong during accept.
        :param user: Proposed operator.
        :param cost: Cost.
        :param time: Car arrival time.
        :param kwargs:
        :return: Nothing
        """
        if self.expiration_date <= timezone.now():
            raise OperationError('Order has expired at %s.' % str(self.expiration_date))

        if self.status == OrderStatus.PROCESSED or self.status not in OrderStatus.sources(OrderStatus.PROCESSED):
            raise OperationError('Order has already processed.')

        cost = cost or self.route.cost
        time = time or self.route.departure_time

        # try to update order
        try:
            # get order and lock it
            orders = Order.objects.select_for_update(nowait=True)\
                .filter(id=self.id, status__in=OrderStatus.sources(OrderStatus.PROCESSED))
            if not orders.exists():
                raise OperationError('Order already processed or doesn\'t exists.')

            order = orders[0]

            # create places for route
            places = self.route.places
            for p in places:
                p.pk = p.id = None
                p.user = self.organization.owner
                p.save()

            # create proposed by operator route
            proposed_route = Route.objects.create_route(user = self.organization.owner, role = 'driver', places = places,
                organization = self.organization, departure_time = time, waiting_time_span = 15, cost = cost,
                distance_extension = 0)

            # create meeting and dropoff
            meeting = Appointment(
                lat = places[0].latitude,
                lon = places[0].longitude,
                address = places[0].address,
                time = time
            )
            meeting.save()

            dropoff = Appointment(
                lat = places[1].latitude,
                lon = places[1].longitude,
                address = places[1].address,
            )
            dropoff.save()

            # create matches
            match = Match(
                from_route=proposed_route,
                to_route=self.route,
                meeting=meeting,
                dropoff=dropoff,
                cost=cost,
                distance=0,
                distance_extension=0,
                status='accepted',
                to_status='new',
                grade=0,
                detour=0,
            )
            match.save()

            other_match = Match(
                from_route=self.route,
                to_route=proposed_route,
                meeting=meeting,
                dropoff=dropoff,
                cost=cost,
                distance=0,
                distance_extension=0,
                status='new',
                to_status='new',
                grade=0,
                detour=0,
            )
            other_match.save()

            order.status = OrderStatus.PROCESSED
            order.match = match
            order.other_match = other_match
            order.save()
            self.refresh()
        except DatabaseError, e:
            raise OperationError('Order is already processing.')

    def set_status(self, status, **kwargs):
        """
        Common method to set order status.
        :param status:
        :param user: Required when set status to accepted.
        :param time: Re
        :param cost:
        :return:
        """
        #check if we know status
        if status not in OrderStatus.ORDER_STATUS_WORKFLOW:
            raise OperationError('Unknown order status "%s". Available values: %s.' % (status, ', '.join(OrderStatus.ORDER_STATUS_WORKFLOW.keys())))
        # remove 'ed' from status and try to get appropriate method to set status.
        meth = status[:-2]
        meth = getattr(self, meth, None)
        if meth:
            meth(**kwargs)
        else:
            self.check_status_transition(status)
            # try to reject order
            try:
                # get unaccepted order, lock it and update
                orders = Order.objects.select_for_update(nowait=True)\
                    .filter(id=self.id, status__in=OrderStatus.sources(status))
                if not orders.exists():
                    raise OperationError('Order already %s or doesn\'t exists.' % status)
                else:
                    order = orders[0]
                    order.status = status
                    order.save()
                    self.refresh()
            except DatabaseError, e:
                logger.error(e.message)
                raise OperationError('Order already %s.' % status)

    def rotate(self, commit=True):
        """
        Create new order for the next organization.
        :return: None if no more organizations to move to, or new order.
        """
        used_organizations = Order.objects.filter(route_id=self.route_id).values_list('organization_id', flat=True)
        organizations = Organization.objects.filter(type='taxi', status='active')\
            .exclude(id__in=used_organizations)\
            .order_by(*['-rating'])
        if not organizations.exists():
            return None

        order = Order()
        order.route = self.route
        order.organization = order.choose_organization(organizations)
        if order.organization:
            order.expiration_date = timezone.now() + timedelta(seconds=ORDER_EXPIRATION_TIME)
            order.modified_date = timezone.now()
            order.created_date = order.modified_date
            if commit:
                order.save()
            return order
        else:
            return None

    def choose_organization(self, organizations):
        """
        Возвращает первую организацию, в чью область попадает маршрут, находящийся в self.route
        """
        for organization in organizations:
            if organization.is_polygon_contains_route(self.route):
                return organization
        return None

    def __unicode__(self):
        result = 'Order for route %d in %s status: %s' % (self.route_id, self.organization.name, self.status)
        return result

    def save(self, *args, **kwargs):
        self.modified_date = timezone.now()
        if not self.created_date:
            self.created_date = self.modified_date
        super(self.__class__, self).save(*args, **kwargs)


from apps.orders.signal_handlers import *
