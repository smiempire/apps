# -*- coding: utf-8 -*-
from celery.task import task
from celery.utils.log import get_task_logger
from apps.operations.models import Operation

logger = get_task_logger(__name__)


@task
def collect_expired_operations():
    collected = Operation.objects.collect_expired()
    logger.info('Collected %d outdated operations.' % collected)
