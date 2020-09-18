# -*- coding: utf-8 -*-
import os
from datetime import timedelta
from celery import task
from celery.utils.log import get_task_logger
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone
from sorl.thumbnail.shortcuts import get_thumbnail, delete
from apps.accounts.settings import AVATAR_THUMBNAILS
from apps.accounts.models import UserProfile, DriverStatus

logger = get_task_logger(__name__)


@task(ignore_result=True)
def generate_thumbnails(image):
    f_name, f_ext = os.path.splitext(image.name)

    # Clear old thumbnails for this image.
    delete(image, delete_file=False)

    for name, params in AVATAR_THUMBNAILS.iteritems():
        try:
            # Create thumbnail and store it in cache.
            thumbnail = get_thumbnail(image, params.get('geometry_string'), **params.get('options'))

            # Save thumbnail copy from cache for backward compatibility.
            img_name = '%s_%s%s' % (f_name, name, f_ext)
            default_storage.save(img_name, ContentFile(thumbnail.read()))
        except IOError:
            continue


@task(ignore_result=True)
def freeze_inactive_users():
    profiles = UserProfile.objects.filter(
        last_activity__lte=timezone.now() - timedelta(days=90),
        is_frozen=False,
    )
    for profile in profiles:
        profile.freeze()


@task(ignore_result=True)
def closed_inactive_users():
    """
    Set status "Closed" for open drivers with waiting more 60 minutes
    """
    profiles = UserProfile.objects.filter(
        last_activity__lte=timezone.now() - timedelta(minutes=60),
        taxi_status=DriverStatus.OPEN
    ).update(taxi_status=DriverStatus.CLOSED)
