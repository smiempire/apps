# -*- coding: utf-8 -*-
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.edit import FormView
from django.forms.util import ErrorDict
from django.conf import settings

from apps.accounts.forms import UserCreationForm, UserAndRouteCreationForm


@csrf_exempt
def create_user(request):
    if not request.user.is_authenticated() or not request.user.is_superuser:
        return HttpResponseForbidden()

    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect('/admin/auth/user')
    else:
        form = UserCreationForm()

    return render(request, 'accounts/create_user.html', {'form': form})


class CreateUserAndRouteView(FormView):
    template_name = 'accounts/create_user_and_route.html'
    form_class = UserAndRouteCreationForm
    success_url = '/create_user_and_route/'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated() or not request.user.is_staff:
            return HttpResponseRedirect('/admin/')
        else:
            return super(CreateUserAndRouteView, self).dispatch(request, *args, **kwargs)

    def render_to_response(self, context, **response_kwargs):
        context['static'] = settings.STATIC_URL
        return super(CreateUserAndRouteView, self).render_to_response(context, **response_kwargs)

    def form_valid(self, form):
        route = form.save()
        stored_form_data = {
            'start_place_country': form.cleaned_data['start_place_country'],
            'start_place_adm_area_level_1': form.cleaned_data['start_place_adm_area_level_1'],
            'start_place_locality': form.cleaned_data['start_place_locality'],

            'finish_place_country': form.cleaned_data['finish_place_country'],
            'finish_place_adm_area_level_1': form.cleaned_data['finish_place_adm_area_level_1'],
            'finish_place_locality': form.cleaned_data['finish_place_locality'],

            'route_timezone': form.cleaned_data['route_timezone'],
        }
        stored_form = self.form_class(stored_form_data)
        stored_form._errors = ErrorDict()
        context = self.get_context_data(form=self.form_class())
        context['form'] = stored_form
        context['is_created'] = True
        context['short_link'] = route.get_short_link()
        return self.render_to_response(context)