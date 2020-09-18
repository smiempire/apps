# -*- coding: utf-8 -*-
from django.db import models
from libs.models import BaseModel


LOG_TYPE_CHOICES = (
    (u'info', u'info'),
    (u'error', u'error'),
)


class Log(BaseModel):
    time = models.DateTimeField(auto_now_add=True, editable=False)
    type = models.CharField(max_length=20, choices=LOG_TYPE_CHOICES, blank=True, default=u'info')
    key = models.CharField(max_length=50, blank=True, null=True)
    text = models.TextField()

    def __unicode__(self):
        return str(self.id)
