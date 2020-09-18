# -*- coding: utf-8 -*-
"""
Этот файл является заглушкой, позволяющей перенаправлять сообщения настоящему подборщику.
"""

from celery import Celery, Task

celery = Celery('matcher')
celery.config_from_object('transmission.settings')


@celery.task(name='matcher.create', queue='matcher')
def create(_route):
    """
    Creates route index in database and performs search for matching routes.
    :param _route: dict with route instance.
    :return: list of matches.
    """
    return []


@celery.task(name='matcher.delete', queue='matcher')
def delete(_id):
    """
    Deletes route index from database.
    :param _id: id of previously stored route instance.
    :return: nothing.
    """
    return


@celery.task(name='matcher.update', queue='matcher')
def update(_route):
    """
    Update route index in database.
    Same as create, but for existing route.
    :param _route: dict with route instance.
    :return: list of matches.
    """
    return create(_route)


@celery.task(name='matcher.clean', queue='matcher')
def clean():
    """
    Clear all routes indexes in database.
    :return: nothing.
    """
    return
