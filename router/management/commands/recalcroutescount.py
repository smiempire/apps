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
                            SET routes_count = r.routes_count
                            FROM (
                                SELECT user_id, Count(id) as routes_count
                                FROM router_route
                                WHERE regular_route_id IS NULL GROUP BY user_id
                            ) AS r
                            WHERE accounts_userprofile.user_id = r.user_id''')
            transaction.commit_unless_managed()
        elif engine.endswith('sqlite3'):
            from django.db.models import Count
            from django.contrib.auth.models import User
            users = User.objects.filter(route__regular_route = None).annotate(routes_count = Count('route'))
            for user in users:
                UserProfile.objects.filter(user_id=user.id).update(routes_count = user.routes_count)
