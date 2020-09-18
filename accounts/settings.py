# -*- coding: utf-8 -*-
import string
from django.conf import settings

DEFAULT_AVATAR_THUMBNAILS = {
    'mini':     {'geometry_string': '24x24', 'options': {'crop': 'center'}},
    'small':    {'geometry_string': '48x48', 'options': {'crop': 'center'}},
    'normal':   {'geometry_string': '64x64', 'options': {'crop': 'center'}},
    'big':      {'geometry_string': '96x96', 'options': {'crop': 'center'}},
    'bigger':   {'geometry_string': '128x128', 'options': {'crop': 'center'}},
}
AVATAR_THUMBNAILS = getattr(settings, 'AVATAR_THUMBNAILS', DEFAULT_AVATAR_THUMBNAILS)

DEFAULT_PHONE_VERIFIER_LENGTH = 6
PHONE_VERIFIER_LENGTH = getattr(settings, 'PHONE_VERIFIER_LENGTH', DEFAULT_PHONE_VERIFIER_LENGTH)

DEFAULT_PHONE_VERIFIER_SYMBOLS = string.digits
PHONE_VERIFIER_SYMBOLS = getattr(settings, 'PHONE_VERIFIER_SYMBOLS', DEFAULT_PHONE_VERIFIER_SYMBOLS)

DEFAULT_PHONE_VERIFIER_LIFETIME = 15 * 60 * 1000
PHONE_VERIFIER_LIFETIME = getattr(settings, 'PHONE_VERIFIER_LIFETIME', DEFAULT_PHONE_VERIFIER_LIFETIME)

DEFAULT_PHONE_VERIFIER_DISPATCH_COUNT = 3
PHONE_VERIFIER_DISPATCH_COUNT = getattr(settings, 'PHONE_VERIFIER_DISPATCH_COUNT', DEFAULT_PHONE_VERIFIER_DISPATCH_COUNT)