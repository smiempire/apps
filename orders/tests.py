# -*- coding: utf-8 -*-
from datetime import timedelta
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from apps.orders.exceptions import OperationError
from apps.orders.models import Order
from apps.organizations.models import Organization
from apps.router.forms import RouteForm
from apps.router.models import Place

class OrdersWorkflowTests(TestCase):

    def setUp(self):
        t = self.taxi_owner = User.objects.create_user('taxi', None, '123456')

        org = self.organization = Organization.objects.create(
            owner = t,
            name = 'v7taxi',
            type = 'taxi',
            status = 'active',
            contact_phone = '+71234567890'
        )

        op = self.operator = User.objects.create_user('operator', None, '123456')
        org.members.add(op)

        u = self.user = User.objects.create_user('test1', None, '123456')

        p1 = self.place1 = Place()
        p1.user = u
        p1.address = 'Place #1'
        p1.latitude = 1
        p1.longitude = 1
        p1.name = 'place1'
        p1.save()

        p2 = self.place2 = Place()
        p2.user = u
        p2.address = 'Place #1'
        p2.latitude = 2
        p2.longitude = 2
        p2.name = 'place2'
        p2.save()


    def create_route(self):
        form = RouteForm({
            'accept_taxi' : 'true',
            'accept_carpool' : 'false',
            'cost' : '100',
            'departure_time' : str(timezone.now() + timedelta(minutes=20)),
            'passengers_count' : '1',
            'places' : '%d,%d' % (self.place1.id, self.place2.id,),
            'role' : 'passenger',
            'user' : str(self.user.id),
            'waiting_time_span' : '20',
            'walking_distance' : '500',
            })
        if not form.is_valid():
            print form.errors
            self.assertTrue(form.is_valid())
        return form.save()


    def test_order_auto_creation(self):
        r = self.create_route()
        orders = Order.objects.filter(route = r)
        self.assertTrue(orders.exists())
        self.assertEqual(len(orders), 1)

        order = orders[0]
        self.assertEqual(order.status, 'new')


    def test_accept_order(self):
        r = self.create_route()
        order = Order.objects.filter(route = r).latest('id')
        order.accept(self.operator)

        orders = Order.objects.filter(route = r, status = 'accepted')
        self.assertTrue(orders.exists())
        self.assertEqual(len(orders), 1)

        with self.assertRaisesMessage(OperationError, 'Order is already accepted by another operator.'):
            order.accept(self.taxi_owner)


    def test_process_order(self):
        r = self.create_route()
        order = Order.objects.filter(route = r).latest('id')
        order.accept(self.operator)
        order.process(timezone.now() + timedelta(minutes=20))

        orders = Order.objects.filter(route = r, status = 'processed')
        self.assertTrue(orders.exists())
        self.assertEqual(len(orders), 1)

        matches = r.matches.filter(to_route__organization = order.organization)
        self.assertTrue(matches.exists())
        self.assertEqual(len(matches), 1)

        with self.assertRaises(OperationError):
            order.process(timezone.now())


    def test_rejection_of_processed_order(self):
        r = self.create_route()
        order = Order.objects.filter(route = r).latest('id')
        order.accept(self.operator)
        order.process(timezone.now() + timedelta(minutes=20))
        matches = r.matches.filter(to_route__organization = order.organization)
        match = matches[0]
        match.status = 'rejected'
        match.save()
        order.refresh()
        self.assertEqual(order.status, 'rejected')
