# -*- coding: utf-8 -*-
from django.db import models
from django.utils import timezone
from recurrence.fields import RecurrenceField


class Parameter(models.Model):
    key = models.SlugField(verbose_name=u'ключ параметра', max_length=255, unique=True)
    description = models.CharField(verbose_name=u'описание параметра', max_length=1024, blank=True, default=u'')
    recurrence = RecurrenceField(verbose_name=u'частота обновления', blank=True, default='')
    enabled = models.BooleanField(verbose_name=u'активен', blank=True, default=True)
    date_created = models.DateTimeField(verbose_name=u'дата создания', editable=False)
    date_modified = models.DateTimeField(verbose_name=u'дата создания', blank=True, null=True, editable=False)

    def __unicode__(self):
        return '%s' % self.key

    def save(self, *args, **kwargs):
        t = timezone.now()
        if not self.date_created:
            self.date_created = t
        self.date_modified = t
        super(Parameter, self).save(*args, **kwargs)


class Value(models.Model):
    parameter = models.ForeignKey(Parameter)
    data = models.FloatField(verbose_name=u'значение параметра')
    date_created = models.DateTimeField(verbose_name=u'дата создания', editable=False)
    date_modified = models.DateTimeField(verbose_name=u'дата создания', editable=False)

    def __unicode__(self):
        return '%s : %s (%s)' % (self.parameter.key, str(self.data), str(self.date_modified))

    def save(self, *args, **kwargs):
        t = timezone.now()
        if not self.date_created:
            self.date_created = t
        self.date_modified = t
        super(Value, self).save(*args, **kwargs)
