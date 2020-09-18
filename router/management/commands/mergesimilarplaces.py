# -*- coding: utf-8 -*-
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from apps.router.models import Place, PlaceInRoute

class Command(BaseCommand):
    help = 'Merges places with same coordinates.'

    def handle(self, *args, **kwargs):
        users = User.objects.all()
        for user in users:
            places = Place.objects.filter(user = user).order_by('latitude', 'longitude', '-last_ride').distinct('latitude', 'longitude')
            print '%s (%d) : %s' % (user.username, user.id, ', '.join([str(x.id) for x in places]),)
            for place in places:
                duplicates = Place.objects.filter(user = user, latitude = place.latitude, longitude = place.longitude).exclude(pk = place.pk)
                print 'Found duplicates for %d: %s' % (place.id, ', '.join([str(x.id) for x in duplicates]),)
                for duplicate in duplicates:
                    print 'Updated routes: %d' % PlaceInRoute.objects.filter(place = duplicate).update(place = place)
                duplicates.delete()
                place.name = place.name.strip()
                place.address = place.address.strip()
                print 'Address before: %s' % place.address
                lines = [s.strip() for s in place.address.split(';')]
                if lines[-1].endswith(lines[0]) and lines.__len__()>1:
                    del(lines[-1])
                    lines.reverse()
                place.address = '; '.join(lines)
                place.save()
                print 'Address after: %s' % place.address
                print '-' * 78
            print '%s\n' % ('=' * 78,)




