# -*- coding: utf-8 -*-
import string
from django.conf import settings
from apps.authentication import settings as auth_settings

DEFAULT_PHONE_VERIFIER_LENGTH = 4
PHONE_VERIFIER_LENGTH = getattr(settings, 'PHONE_VERIFIER_LENGTH', DEFAULT_PHONE_VERIFIER_LENGTH)

DEFAULT_PHONE_VERIFIER_SYMBOLS = string.digits
PHONE_VERIFIER_SYMBOLS = getattr(settings, 'PHONE_VERIFIER_SYMBOLS', DEFAULT_PHONE_VERIFIER_SYMBOLS)

DEFAULT_PHONE_VERIFIER_LIFETIME = 12 * 60 * 60 * 1000
PHONE_VERIFIER_LIFETIME = getattr(settings, 'PHONE_VERIFIER_LIFETIME', DEFAULT_PHONE_VERIFIER_LIFETIME)

DEFAULT_PHONE_VERIFIER_DISPATCH_COUNT = 3
PHONE_VERIFIER_DISPATCH_COUNT = getattr(settings, 'PHONE_VERIFIER_DISPATCH_COUNT', DEFAULT_PHONE_VERIFIER_DISPATCH_COUNT)

LOGIN_REDIRECT_URL = settings.LOGIN_REDIRECT_URL

SIGNIN_ATTEMPTS_COUNT = auth_settings.SIGNIN_ATTEMPTS_COUNT

SIGNIN_BRUTE_FORCE_PROTECTION_PAUSE = auth_settings.SIGNIN_BRUTE_FORCE_PROTECTION_PAUSE
