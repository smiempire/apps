# -*- coding: utf-8 -*-
from apps.logs.models import Log


def log(text, key=None, type='info'):
    Log.objects.create(
        type=type,
        key=key,
        text=text
    )
