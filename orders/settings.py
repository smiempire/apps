# -*- coding: utf-8 -*-
from django.conf import settings

DEFAULT_ORDER_EXPIRATION_TIME = 120
DEFAULT_ORDER_APPROVED_TIME = 600
ORDER_EXPIRATION_TIME = getattr(settings, 'ORDER_EXPIRATION_TIME', DEFAULT_ORDER_EXPIRATION_TIME)
# Время нахождения заказа в состоянии APPROVED, секунды
ORDER_APPROVED_TIME = getattr(settings, 'ORDER_APPROVED_TIME', DEFAULT_ORDER_APPROVED_TIME)
