# -*- coding: utf-8 -*-
from relationships.models import Relationship
from apps.relations.signal_handlers import inc_following_count, dec_following_count
from django.db.models import signals
signals.post_save.connect(inc_following_count, sender=Relationship, dispatch_uid='increment user following counter')
signals.post_delete.connect(dec_following_count, sender=Relationship, dispatch_uid='decrease user following counter')
