# -*- coding: utf-8 -*-
from django.views.generic import TemplateView


class TermsOfUseView(TemplateView):
    template_name = 'authentication/terms_of_use.html'

    def render_to_response(self, context, **response_kwargs):
        context['params']['query_string'] = self.request.META['QUERY_STRING']
        return super(TermsOfUseView, self).render_to_response(context, **response_kwargs)


class SpamView(TemplateView):
    template_name = 'authentication/spam.html'

    def render_to_response(self, context, **response_kwargs):
        context['params']['query_string'] = self.request.META['QUERY_STRING']
        return super(SpamView, self).render_to_response(context, **response_kwargs)