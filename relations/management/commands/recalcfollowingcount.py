# -*- coding: utf-8 -*-
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import router
from apps.accounts.models import UserProfile

__docformat__ = 'restructuredtext ru'

class Command(BaseCommand):
    help = 'Recalculates users routes counters.'

    def handle(self, *args, **options):
        # determine database backend
        using = router.db_for_write(UserProfile)
        database = settings.DATABASES.get(using)
        if not database:
            return

        engine = database.get('ENGINE')
        if not engine:
            return

        if engine.endswith('postgresql_psycopg2'):
            from django.db import connections, transaction
            cursor = connections[using].cursor()
            cursor.execute('''UPDATE accounts_userprofile
                            SET following_count = f.following_count
                            FROM (
                                SELECT from_user_id, Count(id) as following_count
                                FROM relationships_relationship
                                WHERE status_id = (
                                    SELECT id
                                    FROM relationships_relationshipstatus
                                    WHERE from_slug = 'following'
                                )
                                GROUP BY from_user_id
                            ) AS f
                            WHERE accounts_userprofile.user_id = f.from_user_id;''')
            transaction.commit_unless_managed()
        elif engine.endswith('sqlite3'):
            from django.db.models import Count
            from django.contrib.auth.models import User
            users = User.objects.filter(from_users__status__from_slug = 'following').annotate(following_count = Count('from_users'))
            for user in users:
                UserProfile.objects.filter(user_id=user.id).update(following_count = user.following_count)
