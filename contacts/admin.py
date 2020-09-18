# -*- coding: utf-8 -*-
from apps.contacts.models import Contact, PhoneNumber, EmailAddress
from libs.admin import admin
from django.contrib.contenttypes.generic import GenericTabularInline


class PhoneNumberInline(GenericTabularInline):
    model = PhoneNumber
    ct_field = 'content_type'
    ct_fk_field = 'object_id'
    extra = 1


class EmailAddressInline(GenericTabularInline):
    model = EmailAddress
    ct_field = 'content_type'
    ct_fk_field = 'object_id'
    extra = 1


class ContactAdmin(admin.ModelAdmin):
    inlines = (PhoneNumberInline, EmailAddressInline)
    list_display = ('last_name', 'first_name', 'middle_name', 'source_uid',)


class PhoneNumberAdmin(admin.ModelAdmin):
    search_fields = ['phone_number']
    list_display = ('id', 'phone_number', 'object_id', 'is_verified', 'is_main', 'is_active')
    list_display_links = ['phone_number']


admin.site.register(Contact, ContactAdmin)
admin.site.register(PhoneNumber, PhoneNumberAdmin)