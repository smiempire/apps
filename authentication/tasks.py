# -*- coding: utf-8 -*-
from celery import task
from celery.utils.log import get_task_logger
from django.core import management
from django.db import connection, transaction

logger = get_task_logger(__name__)

@task(ignore_result=True)
def clean_expired_sessions():
    management.call_command('cleanup')


@task(ignore_result=True)
def clean_oauth_nonces():
    cursor = connection.cursor()
    cursor.execute('DELETE FROM piston_nonce')
    transaction.commit_unless_managed()
