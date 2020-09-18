# -*- coding: utf-8 -*-
from django.utils import timezone
from celery import task, chain

from apps.router.forms import AppointmentForm, MatchForm
from apps.router.models import Route, Match, PushType
from apps.matcher.stub_tasks import update
from apps.messaging.notifications import MatchStatusNotification
from apps.messaging.tasks import send_notification, send_push


@task(ignore_result=True)
def save_matches(matches):
    """
    Сохраняет совпадения маршрутов, возвращённые подборщиком.
    """
    for match in matches:
        # Сохраняем матчи, только если маршруты существуют и активны.
        driver_route = Route.objects.filter(id=match['driver'], status='active')
        passenger_route = Route.objects.filter(id=match['rider'], status='active')
        if not (driver_route and passenger_route):
            continue

        # Генерируем вручную поля, которые не возвращает новый подборщик.
        driver_distance = 0
        driver_distance_extension = match['detour'] / driver_distance if driver_distance > 0 else 0
        passenger_distance = 0
        passenger_distance_extension = match['detour'] / passenger_distance if driver_distance > 0 else 0

        driver_route = Route.objects.get(id=match['driver'])
        passenger_route = Route.objects.get(id=match['rider'])
        cost = driver_route.cost if driver_route.cost > 0 else passenger_route.cost

        # Сохраняем встречу.
        meeting = {
            'name': '',
        }
        meeting_form = AppointmentForm(meeting)
        if not meeting_form.is_valid():
            continue
        meeting = meeting_form.save()

        # Сохраняем высадку.
        dropoff = {
            'name': '',
        }
        dropoff_form = AppointmentForm(dropoff)
        if not dropoff_form.is_valid():
            continue
        dropoff = dropoff_form.save()

        # Сохраняем соответствие для водителя.
        driver_match = {
            'from_route': match['driver'],
            'to_route': match['rider'],
            'meeting': meeting.id,
            'dropoff': dropoff.id,
            'cost': cost,
            'distance': driver_distance,
            'distance_extension': driver_distance_extension,
            'status': match.get('driver_status') or 'new',
            'to_status': match.get('rider_status') or 'new',
            'grade': match['grade'],
            'detour': match['detour'],
        }
        driver_match_form = MatchForm(driver_match)
        if not driver_match_form.is_valid():
            continue
        if not Match.objects.filter(from_route=match['driver'], to_route=match['rider']):
            driver_match = driver_match_form.save()

        # Сохраняем соответствие для пассажира.
        passenger_match = {
            'from_route': match['rider'],
            'to_route': match['driver'],
            'meeting': meeting.id,
            'dropoff': dropoff.id,
            'cost': cost,
            'distance': passenger_distance,
            'distance_extension': passenger_distance_extension,
            'status': match.get('rider_status') or 'new',
            'to_status': match.get('driver_status') or 'new',
            'grade': match['grade'],
            'detour': match['detour'],
        }
        passenger_match_form = MatchForm(passenger_match)
        if not passenger_match_form.is_valid():
            continue
        if not Match.objects.filter(from_route=match['rider'], to_route=match['driver']):
            passenger_match = passenger_match_form.save()

        # оповещаем маршрут, который был создан раньше, о новом попутчике (если этот попутчик входит в топ-10)
        match_for_notice = driver_match if driver_route.date_created < passenger_route.date_created else passenger_match
        top_matches = Match.objects.filter(
            from_route=match_for_notice.from_route,
        ).exclude(
            status='new',
            to_status='new',
            is_canceled=True,
        ).order_by(
            '-grade',
        )[:10]

        if match_for_notice in top_matches:
            # Push for passenger about new driver
            message = PushType.values[PushType.FOUND_NEW_DRIVER]
            data = {
                'push_type': PushType.FOUND_NEW_DRIVER,
                'route_id': match_for_notice.from_route.id,
                'match_id': match_for_notice.id,
            }
            send_push(match_for_notice.to_route.user.id, message, data)


@task(ignore_result=True)
def update_matches(new_matches, route_id):
    """
    Сравнивает имеющиеся подборы для указанного маршрута с новыми и обновляет их соответствующим образом.
    """
    old_matches = Match.objects.filter(from_route=route_id)
    for old_match in old_matches:
        # достаем симметричный матч
        to_match = Match.objects.get(from_route=old_match.to_route, to_route=old_match.from_route)

        # ищем старый матч в новых
        is_match_found = False
        for new_match in new_matches:
            if (old_match.from_route.id == new_match['driver'] and old_match.to_route.id == new_match['rider']) or \
                    (old_match.from_route.id == new_match['rider'] and old_match.to_route.id == new_match['driver']):
                is_match_found = True

                # from_route = Route.objects.get(id=old_match.from_route.id)
                # to_route = Route.objects.get(id=old_match.to_route.id)

                # Сохраняем соответствие для to_route.
                to_match.grade = new_match['grade']
                to_match.detour = new_match['detour']

                # Сохраняем соответствие для from_route.
                old_match.grade = new_match['grade']
                old_match.detour = new_match['detour']

                if old_match.status != 'rejected':
                    # если матч был отменен, но после обновления маршрута подобрался вновь
                    if old_match.is_canceled:
                        to_match.is_canceled = False
                        old_match.is_canceled = False
                        if old_match.to_status == 'accepted':
                            # TODO: push to_route.user_id с сообщением, что его попутчик снова активен
                            pass
                    elif old_match.to_status == 'accepted':
                        # TODO: push to_route.user_id с сообщением, что его попутчик обновил маршрут
                        pass

                to_match.save()
                old_match.save()

        # если в новых матчах нет старого, то ставим флаг canceled
        if not is_match_found and not old_match.is_canceled and old_match.status != 'rejected':
            to_match.is_canceled = True
            old_match.is_canceled = True
            to_match.save()
            old_match.save()
            if old_match.to_status == 'accepted':
                # TODO: push to_route.user_id с сообщением, что его попутчик отменил поездку
                pass

    # отбираем новые матчи, которых не было до обновления маршрута, и сохраняем их обычным способом
    to_save_matches = []
    for new_match in new_matches:
        for old_match in old_matches:
            if not ((old_match.from_route.id == new_match['driver'] and old_match.to_route.id == new_match['rider']) or
                    (old_match.from_route.id == new_match['rider'] and old_match.to_route.id == new_match['driver'])):
                to_save_matches.append(new_match)
    if to_save_matches:
        save_matches.delay(to_save_matches)


@task(ignore_result=True)
def send_active_routes_to_matcher():
    """
    Посылает все активные маршруты (у которых departure_time не истекло),
    находящиеся в системе на данный момент, в подборщик.
    Все ответы, полученные от подборщика игнорируются.
    Данную задачу необходимо выполнять при смене подборщика (или его базы данных) на production-сервере,
    чтобы активные маршруты не терялись и продолжали участвовать в поиске.
    """
    from apps.matcher.models import prepare_route_data
    active_routes = Route.objects.filter(departure_time__gte=timezone.now())
    for route in active_routes:
        route_data = prepare_route_data(route)
        if route_data:
            chain(update.s(route_data), update_matches.s(route_data['id'])).apply_async()
