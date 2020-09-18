# -*- coding: utf-8 -*-
from django.contrib.contenttypes.models import ContentType
from django.db.models import Model, CharField, ForeignKey
from django.utils.translation import ugettext_lazy as _

EVENT_CHOICES = (
    ('create', _(u'Создать')),
    ('edit', _(u'Изменить')),
    ('delete', _(u'Удалить')),
)

class EventMessage(Model):
    content_type = ForeignKey(ContentType, related_name='event_message_set')
    event = CharField(verbose_name=u'событие', choices=EVENT_CHOICES, max_length=9)
    message = CharField(verbose_name=u'текст сообщения', max_length=255)


    def __unicode__(self):
        return self.message


    @classmethod
    def get_message(cls, model, event, *args, **kwargs):
        """
        Возвращает произвольное сообщение для указанного события указанной модели.
        Пустая строка в результате означает, что для данного события данной модели нет сообщений.
        """
        content_type = ContentType.objects.get(model=model.__name__.lower())
        ems = cls.objects.filter(content_type=content_type, event=event).order_by('?')
        if not ems:
            return ''
        em = ems[0]
        return em.message