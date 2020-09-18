# -*- coding: utf-8 -*-
from datetime import timedelta
import random
import re
from django.contrib.auth.models import User
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext as _

from apps.contacts import settings
from apps.messaging.tasks import send_viber_or_sms, send_sms, send_wa_or_sms
from apps.operations.settings import DEFAULT_OPERATION_EXPIRATION_PERIOD


class ContactDetail(models.Model):
    content_type = models.ForeignKey(ContentType)
    object_id = models.IntegerField(db_index=True)
    content_object = generic.GenericForeignKey()

    """
    TODO:
    1) add type and value fields,
    2) make class non abstract,
    3) move all PhoneNumbers and EmailAddresses to this table with appropriate types,
    4) refactor Contacts API handlers to work with this table,
    5) refactor authentication to store phones and emails here, instead PhoneNumber and EmailAddress tables,
    6) remove PhoneNumber and EmailAddress tables and models.
    """

    is_verified = models.BooleanField(_(u'is verified'), blank=True, default=False)
    is_main = models.BooleanField(_(u'is main'), blank=True, default=False)
    is_active = models.BooleanField(_(u'is active'), blank=True, default=False)
    date_created = models.DateTimeField(_('date added'), auto_now_add=True)
    date_modified = models.DateTimeField(_('date modified'), auto_now=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.is_verified = False if self.is_verified is None else self.is_verified
        self.is_main = False if self.is_main is None else self.is_main
        self.is_active = False if self.is_active is None else self.is_active
        super(ContactDetail, self).save(*args, **kwargs)


class PhoneNumber(ContactDetail):
    phone_number = models.CharField(_('number'), max_length=50, db_index=True)

    def __unicode__(self):
        return self.phone_number

    @classmethod
    def format(cls, phone):
        """
        Очищает номер телефона от лишних сиволов и форматирует.
        """
        result = re.sub(r'[^\d\+x]', '', phone)
        if result.startswith('8') and len(result) == 11:
            result = '%s%s' % ('+7', result[1:],)
        return result

    @classmethod
    def generate_verifier(cls, symbols=None, length=None):
        s = symbols or settings.PHONE_VERIFIER_SYMBOLS
        l = length or settings.PHONE_VERIFIER_LENGTH
        return ''.join(random.choice(s) for x in range(l))

    @classmethod
    def get_verifier_expiration_date(cls, milliseconds=None):
        ms = milliseconds or settings.DEFAULT_PHONE_VERIFIER_LIFETIME
        return timezone.now() + timedelta(milliseconds=ms)

    @classmethod
    def send_verifier(cls, phone, verifier, message_tpl=None, is_repeat=False, operation=None,
                      client=None, whatsapp=False, viber=False, sender=None):
        code_life_time = DEFAULT_OPERATION_EXPIRATION_PERIOD / 60 / 1000
        tpl = message_tpl or u'Код подтверждения номера телефона: %(verifier)s.'
        params = {
            'verifier': verifier,
            'time': code_life_time,
        }

        send_sms(tpl % params, phone, sender)

        # # TODO: на вайбер пока не отправляем, всегда отсылаем смс
        # send_sms(tpl % params, phone)
        # if not is_repeat:
        #     # send_wvs.delay(phone, tpl % params, operation)
        #     # send_viber_or_sms.delay(tpl % params, phone)
        #
        #     if not client or client == 'web':
        #         # TODO: включить это и убрать send_viber_or_sms, когда будет работать whatsapp
        #         # send_wvs.delay(phone, tpl % params, operation)
        #         send_viber_or_sms.delay(tpl % params, phone)
        #     # TODO: включить это, когда будет работать whatsapp
        #     # elif whatsapp:
        #     #     send_wvs.delay(phone, tpl % params, operation)
        #     elif viber:
        #         send_viber_or_sms.delay(tpl % params, phone)
        #     else:
        #         send_sms(tpl % params, phone)
        # else:
        #     send_sms(tpl % params, phone)


class EmailAddress(ContactDetail):
    email_address = models.EmailField(_('address'), db_index=True)

    def __unicode__(self):
        return self.email_address

    regex = re.compile(
        r'[a-z0-9!#$%&\'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&\'*+/=?^_`{|}~-]+)*@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+(?:[A-Z]{2}|com|org|net|edu|gov|mil|biz|info|mobi|name|aero|asia|jobs|museum)\b',
        re.IGNORECASE
    )


class Contact(models.Model):
    owner = models.ForeignKey(User, related_name='contacts')
    user = models.ForeignKey(User, related_name='linked_contacts', blank=True, null=True)
    first_name = models.CharField(_('first name'), max_length=255, blank=True)
    last_name = models.CharField(_('last name'), max_length=255, blank=True)
    middle_name = models.CharField(_('middle name'), max_length=255, blank=True)
    phones = generic.GenericRelation(PhoneNumber)
    emails = generic.GenericRelation(EmailAddress)
    source_uid = models.CharField(_('contact source'), max_length=32, default='')
    batch_uid = models.CharField(_('batch uid'), max_length=32, default='')

    def __unicode__(self):
        if self.user_id:
            return self.user.userprofile.salutation

        full_name_list = [self.first_name, self.middle_name, self.last_name]
        full_name_list = [x for x in full_name_list if x]
        if full_name_list:
            return ' '.join(full_name_list)

        phones = self.phones.all()
        if phones:
            return phones[0].phone_number

        emails = self.emails.all()
        if emails:
            return emails[0].email_address