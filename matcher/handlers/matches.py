# -*- coding: utf-8 -*-
from copy import copy
from django.db.models.query import QuerySet
from piston.utils import rc
from api_v1.handlers.accounts import AccountHandler, UserProfileHandler
from libs.piston_extensions.handlers import CollectionBaseHandler, CountBaseHandler, ResourceBaseHandler
from apps.matcher.forms import MatchForm
from apps.matcher.models import Match, Place, MATCH_STATUS_WORKFLOW
from apps.router.models import Route
from django.utils.translation import ugettext_lazy as _

__docformat__ = 'restructuredtext ru'

class MatchesHandler(CollectionBaseHandler):
    model = Match
    form_class = MatchForm
    exclude = ('match_request', 'matched_request', 'companion__password')
    allowed_methods = ('GET',)

    def read(self, request, *args, **kwargs):
        if not request.user.is_authenticated():
            return rc.FORBIDDEN

        # Добавляем фильтр по юзеру, чтобы никто кроме владельца не мог просмотреть результаты подбора.
        kwargs.update({'match_request__route__user' : request.user})
        instances = self._get(request, *args, **kwargs)

        fields = request.GET.get('fields', '').split(',') if request.GET.get('fields', '') else list(self.fields)

        is_old_client = 'HTTP_USER_AGENT' in request.META and request.META['HTTP_USER_AGENT'] in ['ru.ktovputi.android-v1.1.3b', 'ru.ktovputi.android-v1.1.4b']

        results = self.values(
            instances,
            self.model,
            [f for f in fields if not '__' in f and f not in ['companion', 'companion_route', 'meeting', 'dropoff']],
            [e for e in self.exclude if not '__' in e], iso8601=not is_old_client
        )

        companion_fields = self.subfields('companion', fields)

        companion_route_fields = self.subfields('companion_route', fields)
        companion_route_exclude = self.subfields('companion_route', self.exclude)

        meeting_fields = self.subfields('meeting', fields)
        meeting_exclude = self.subfields('meeting', self.exclude)

        dropoff_fields = self.subfields('dropoff', fields)
        dropoff_exclude = self.subfields('dropoff', self.exclude)

        # Добавляем в список подобранных заявок данные о пользователях и маршрутах.

        if (not fields) or companion_fields or 'companion' in fields:
            sub_request = copy(request)
            sub_request.GET = {}
            if companion_fields:
                sub_request.GET.update({ 'fields' : ','.join(companion_fields), })
            for i, r in enumerate(results):
                inst = instances[i]
                route = inst.matched_request.route
                user = route.user
                r.update({
                    'companion' : AccountHandler().read(request=sub_request, **{'id' : user.id,}),
                    })
                # TODO: Вынести эту хрень в AccountHandler
                userprofile_fields = self.subfields('userprofile', companion_fields)
                if (not companion_fields) or userprofile_fields or 'userprofile' in companion_fields:
                    sub_request = copy(request)
                    sub_request.GET = {}
                    if userprofile_fields:
                        sub_request.GET.update({ 'fields' : ','.join(userprofile_fields), })
                    userprofile_handler = UserProfileHandler()
                    userprofile_handler.public_fields += ('phone',)
                    r['companion'].update({
                        'userprofile' : userprofile_handler.read(request=sub_request, **{'user_id' : user.id,}),
                        })

        # TODO: Удалить после перехода всех на v1.1.6b
        if (not fields) or companion_route_fields or 'companion_route' in fields:
            for i,r in enumerate(results):
                inst = instances[i]
                route = inst.matched_request.route
                user = route.user
                r.update({
                    'companion_route' : self.values(
                        instance = route,
                        model = Route,
                        fields = companion_route_fields,
                        exclude = companion_route_exclude,
                        iso8601 = not is_old_client),
                    })

        if (not fields) or meeting_fields or 'meeting' in fields:
            for i,r in enumerate(results):
                inst = instances[i]
                r.update({
                    'meeting' : self.values(
                        instance = inst.meeting,
                        model = Place,
                        fields = meeting_fields,
                        exclude = meeting_exclude,
                        iso8601 = not is_old_client),
                    })
        if (not fields) or dropoff_fields or 'dropoff' in fields:
            for i,r in enumerate(results):
                inst = instances[i]
                r.update({
                    'dropoff' : self.values(
                        instance = inst.dropoff,
                        model = Place,
                        fields = dropoff_fields,
                        exclude = dropoff_exclude,
                        iso8601 = not is_old_client),
                    })

        return results



class MatchesCountHandler(CountBaseHandler):
    model = Match

    def read(self, request, *args, **kwargs):
        if not request.user.is_authenticated():
            return rc.FORBIDDEN
            # Добавляем фильтр по юзеру, чтобы никто кроме владельца не мог просмотреть результаты подбора.
        kwargs.update({' match_request__route__user' : request.user})
        return super(MatchesCountHandler, self).read(request, *args, **kwargs)



class MatchHandler(ResourceBaseHandler):
    model = Match
    form_class = MatchForm
    exclude = ('match_request', 'matched_request',)
    readonly_fields = ('id', 'match_request', 'matched_request', 'meeting', 'dropoff', 'cost', 'distance', 'distance_extension',)
    allowed_methods = ('GET', 'PUT',)

    def read(self, request, *args, **kwargs):
        if not request.user.is_authenticated():
            return rc.FORBIDDEN

        # Добавляем фильтр по юзеру, чтобы никто кроме владельца не мог просмотреть результаты подбора.
        kwargs.update({'match_request__route__user' : request.user})
        resp = MatchesHandler().read(request, *args, **kwargs)
        if isinstance(resp, (list, QuerySet)) and len(resp):
            return resp[0]
        else:
            return resp


    def update(self, request, *args, **kwargs):
        if not request.user.is_authenticated():
            return rc.FORBIDDEN

        # Добавляем фильтр по юзеру, чтобы никто кроме владельца не мог изменить результаты подбора.
        kwargs.update({'match_request__route__user' : request.user})
        try:
            inst = self.model.objects.get(**kwargs)
        except self.model.DoesNotExist, e:
            return rc.NOT_FOUND
        except self.model.MultipleObjectsReturned:
            return rc.DUPLICATE_ENTRY

        # Проверка соответствия данных логике переходов состояний результата подбора.
        data = request.POST.copy()
        status = data.get('status')
        if status and status not in MATCH_STATUS_WORKFLOW.get(inst.status, []):
            resp = rc.BAD_REQUEST
            resp.content = _('Change status from ''%s'' to ''%s'' is prohibited.')
            return resp

        return super(MatchHandler, self).update(request, *args, **kwargs)
