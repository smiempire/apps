# -*- coding: utf-8 -*-
from django.conf.urls import url, patterns
from piston.authentication import NoAuthentication
from piston.resource import Resource
from api_v1 import settings
from apps.matcher.handlers.matches import MatchesHandler, MatchesCountHandler
from apps.matcher.handlers.matcher import MatcherHandler
from apps.matcher.handlers.matches import MatchHandler

__docformat__ = 'restructuredtext ru'

auth = settings.REST_AUTH
no_auth = NoAuthentication()

# matches_handler = CsrfExemptResource(MatchesHandler, authentication=auth)
# match_handler = CsrfExemptResource(MatchHandler, authentication=auth)
# matches_count_handler = Resource(MatchesCountHandler, authentication=auth)
matcher_handler = Resource(MatcherHandler, authentication=no_auth)

urlpatterns = patterns('',
#    url(r'^routes/(?P<match_request__route_id>\d+)/matches/count\.(?P<emitter_format>.+)$', matches_count_handler),
#    url(r'^routes/(?P<match_request__route_id>\d+)/matches\.(?P<emitter_format>.+)$', matches_handler),
#    url(r'^matches/(?P<id>\d+)\.(?P<emitter_format>.+)$', match_handler),
    url(r'^matcher$', matcher_handler, name='matcher_interface')
)

urlpatterns += patterns('apps.matcher.views',
    url(r'^admin/matcher/cmd.html$', 'cmd'),
)