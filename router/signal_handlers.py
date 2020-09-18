# -*- coding: utf-8 -*-
from django.db.models import F
from django.db.models import signals
from apps.accounts.models import UserProfile
from apps.router.models import Route
from apps.router.models import Match
from django.db.models import Q


def calculate_routes_count(sender, instance, created, **kwargs):
    """
    Calculate userprofile.routes_count.
    """
    routes_count = Route.objects.filter(user=instance.user, regular_route=None).exclude(status='canceled').count()
    UserProfile.objects.filter(user=instance.user).update(routes_count=routes_count)


def sync_symmetric_matches(sender, instance, **kwargs):
    """
    Synchronize symmetrical matches statuses.
    Connect to post_save signal of Match model.
    """
    if not isinstance(instance, Match):
        return

    matches = Match.objects.filter(
        from_route_id=instance.to_route_id,
        to_route_id=instance.from_route_id,
    ).exclude(to_status=instance.status)
    if matches.exists():
        match = matches.latest('id')
        match.to_status = instance.status
        match.save()

    # если оба согласны ехать, то запоминаем, с кем поедет пассажир
    if instance.status == 'accepted' and instance.to_status == 'accepted' and instance.from_route.role == 'passenger' and not instance.is_canceled:
        instance.from_route.driver_route = instance.to_route
        instance.from_route.save(send_to_matcher=False)
        # если это таксишный маршрут, то отменяем все остальные предложения
        if instance.from_route.accept_taxi and instance.from_route.role == 'passenger':
            matches = Match.objects.filter(
                to_route=instance.from_route,
                status='accepted',
                from_route__accept_taxi=True,
                from_route__status='active',
                from_route__role='driver',
            ).exclude(from_route=instance.to_route)
            routes_ids = [match.from_route_id for match in matches]
            routes = Route.objects.filter(id__in=routes_ids)
            for route in routes:
                route.cancel(send_to_matcher=False)
        # устанавливаем водителю статус working
        instance.to_route.user.userprofile.taxi_status = u'working'
        instance.to_route.user.userprofile.save()
    # если никто не хочет везти пассажира, то сбрасываем driver_route
    elif instance.from_route.role == 'passenger':
        accepted_count = Match.objects.filter(
            from_route=instance.from_route,
            status='accepted',
            to_status='accepted',
            to_route__status='active',
        ).count()
        if accepted_count == 0:
            instance.from_route.driver_route = None
            instance.from_route.save(send_to_matcher=False)
    # если отменяется таксишный заказ, то устанавливаем водителю статус open
    if instance.from_route.accept_taxi and instance.from_route.role == u'driver' and (u'rejected' in [instance.status, instance.to_status] or instance.is_canceled):
        instance.from_route.user.userprofile.taxi_status = u'open'
        instance.from_route.user.userprofile.save()




def cancel_matches(sender, instance, **kwargs):
    """
    Отменяет матчи при отмене маршрута.
    """
    if instance.status == 'canceled':
        Match.objects.filter(Q(from_route=instance) | Q(to_route=instance)).update(is_canceled=True)


signals.post_save.connect(calculate_routes_count, sender=Route)
signals.post_save.connect(sync_symmetric_matches, sender=Match)
signals.post_save.connect(cancel_matches, sender=Route)