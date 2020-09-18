# -*- coding: utf-8 -*-
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from apps.authentication.phone import operations


class PhoneNumberPasswordBackend(ModelBackend):
    """
    Authenticates user by associated active PhoneNumber and Password.
    """
    def authenticate(self, phone=None, password=None):
        try:
            user = User.objects.get(userprofile__phones__phone_number=phone, userprofile__phones__is_active=True,
                                    userprofile__phones__is_verified=True)
            if user.check_password(password):
                return user
        except User.DoesNotExist:
            return None


class SmsBackend(ModelBackend):
    """
    Authenticates user by PhoneNumber and randomly generated one time password.
    """
    def authenticate(self, phone=None, password=None):
        try:
            user = User.objects.get(userprofile__phones__phone_number=phone, userprofile__phones__is_active=True,
                                    userprofile__phones__is_verified=True)
            operation = user.operations.get(status='new',
                                            operation_key=operations.SIGNIN_BY_SMS)
            if password in operation.data['verifiers']:
                return user
        except ObjectDoesNotExist:
            return None
