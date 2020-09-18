# -*- coding: utf-8 -*-
from django import forms
from apps.contacts.models import Contact, PhoneNumber, EmailAddress


class PhoneNumberForm(forms.ModelForm):
    class Meta:
        model = PhoneNumber



class EmailAddressForm(forms.ModelForm):
    class Meta:
        model = EmailAddress



class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact