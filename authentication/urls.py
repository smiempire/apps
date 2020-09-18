# -*- coding: utf-8 -*-
from django.conf.urls import patterns, url, include
from django.core.urlresolvers import reverse_lazy
from django.views.generic.base import RedirectView

from phone.urls import urlpatterns as phone_urlpatterns
from apps.authentication.views import TermsOfUseView, SpamView

urlpatterns = patterns(
    '',
    # default auth urls
    url(r'^signup/', RedirectView.as_view(url=reverse_lazy('signup_by_phone'), permanent=False, query_string=True),
        name='signup'),
    url(r'^signin/', RedirectView.as_view(url=reverse_lazy('signin_by_sms'), permanent=False, query_string=True),
        name='signin'),
    # old sign in
    # url(r'^signin/', RedirectView.as_view(url=reverse_lazy('signin_by_phone'), permanent=False, query_string=True),
    #     name='signin'),

    url(r'^phone/', include(phone_urlpatterns)),

    url(r'^terms_of_use/(?P<uid>[\w\d-]+)/', TermsOfUseView.as_view(), name='terms_of_use'),
    url(r'^spam/', SpamView.as_view(), name='spam'),
)
