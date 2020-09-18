# -*- coding: utf-8 -*-

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User

from apps.operations.operations import SIGNIN_BY_OPERATION
from apps.operations.models import Operation
from apps.contacts.models import PhoneNumber
from apps.accounts.models import generate_username


class OperationBackend(ModelBackend):
    """
    Authenticates user by requested operation UID and its verifier.
    """

    def authenticate(self, uid=None, phone=None, verifier=None):
        """
        If phone number already belongs by user, then return this user,
        else create new user
        """

        if not uid and not phone:
            return None

        params = {
            'status': Operation.NEW,
            'operation_key': SIGNIN_BY_OPERATION,
        }
        if uid:
            params['uid'] = uid
        if phone:
            params['key'] = phone

        # Get operation
        try:
            operation = Operation.objects.get(**params)
        except (Operation.DoesNotExist, Operation.MultipleObjectsReturned):
            return None

        # Check last verifier
        if verifier != operation.data['verifiers'][-1]:
            return None

        phone = operation.data['phone']
        try:
            # Get user
            user = User.objects.get(
                userprofile__phones__phone_number=phone,
                userprofile__phones__is_active=True,
                userprofile__phones__is_verified=True
            )
        except User.DoesNotExist:
            # Create new user
            user = User()
            user.username = generate_username()
            password = User.objects.make_random_password()
            user.set_password(password)
            user.save()
            PhoneNumber.objects.create(
                content_object=user.userprofile,
                phone_number=phone,
                is_verified=True,
                is_active=True,
                is_main=True,
            )

        operation.status = Operation.DONE
        operation.save()

        return user
