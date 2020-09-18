# -*- coding: utf-8 -*-
import json
import urllib
import urllib2
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response
from django.utils import timezone
from apps.matcher.forms import MatcherCmdForm
from apps.matcher.models import MatchRequest
from django.conf import settings

__docformat__ = 'restructuredtext ru'

def cmd(request):
    if not request.user.is_superuser:
        return HttpResponseRedirect('/admin/')

    timezone.activate(timezone.get_default_timezone())

    response = None
    if request.method == 'POST':
        form = MatcherCmdForm(request.POST)
        if form.is_valid():
            command = form.cleaned_data['command']
            data = form.cleaned_data['data']
            if form.cleaned_data['method'] == 'POST':
                data = { 'json' : json.dumps(data) }
                data = urllib.urlencode(data)
            else:
                command += '?%s' % urllib.urlencode(data)
                data = None

            try:
                result = urllib2.urlopen(
                    '/'.join([settings.MATCHER_BASE_URL, command]),
                    data
                )
                response = result.read()
            except (urllib2.HTTPError, urllib2.URLError), e:
                response = 'Error %s: %s' % (e.code, e.message)
    else:
        form = MatcherCmdForm()

    match_requests = MatchRequest.objects.filter(route__user=request.user).order_by('id').reverse()[:10]

    context = {
        'form' : form,
        'response' : response,
        'match_requests' : match_requests,
    }

    return render_to_response('matcher/cmd.html', request=request, context=context)