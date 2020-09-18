# -*- coding: utf-8 -*-
import os
from django.contrib.auth.models import User
from django.db.models.signals import post_save, pre_save
from django.utils import timezone
from apps.accounts import tasks
from apps.accounts.models import UserProfile
from apps.router.models import Match


def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(
            user=instance,
            last_activity=timezone.now(),
            defaults={
                'first_name': instance.first_name,
                'last_name': instance.last_name
            }
        )
post_save.connect(create_user_profile, sender=User)


def forward_names_to_userprofile(sender, instance, raw, **kwargs):
    # if instance doesn't have pk, then all work will be done by create_user_profile handler
    if instance.pk and not raw:
        old_instance = User.objects.get(id=instance.pk)
        fwd_fields = ('first_name', 'last_name')
        for field in fwd_fields:
            new_val = getattr(instance, field, '')
            old_val = getattr(old_instance, field, '')
            if new_val != old_val:
                setattr(instance.userprofile, field, new_val)
        instance.userprofile.save()
pre_save.connect(forward_names_to_userprofile, sender=User)


def generate_thumbnails(sender, instance, **kwargs):
    if instance.image:
        tasks.generate_thumbnails.delay(instance.image)
post_save.connect(generate_thumbnails, sender=UserProfile)


def calculate_userprofile_rating(sender, instance, **kwargs):
    instance.to_route.user.userprofile.calculate_rating()
post_save.connect(calculate_userprofile_rating, sender=Match)
