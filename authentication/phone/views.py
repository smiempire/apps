# -*- coding: utf-8 -*-
"""
                                                              |-[ user choose to sign in ]-> SigninSendVerifierView -> SigninCompleteView
                   |-[ users exists ]-> SignupOrSigninView -> |
SignupStartView -> |                                          |-[ user choose to sign up ]-> |
                   |                                                                         |-> SignupSendVerifierView -> SignupCompleteView
                   |-----------------------------------------------------------------------> |
"""
from datetime import timedelta
import random
from django.contrib.auth import login, REDIRECT_FIELD_NAME
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse_lazy
from django.http import HttpResponseRedirect
from django.utils import timezone
from django.views.generic import FormView, RedirectView, View, DetailView, TemplateView
from django.views.generic.detail import SingleObjectMixin
from apps.accounts.models import generate_username
from apps.authentication.phone import operations, settings
from apps.authentication.phone.forms import SignupStartForm, SignupCompleteForm, SigninBySmsStartForm, SigninForm,\
    SigninBySmsCompleteForm, FillUserProfileForm
from apps.contacts.models import PhoneNumber
from apps.messaging.tasks import send_wvs, send_viber_or_sms
from apps.operations.models import Operation
from apps.operations.settings import DEFAULT_OPERATION_EXPIRATION_PERIOD


class ForwardQueryStringMixin(object):
    query_string = True

    def forward_query_string(self, target_url, **kwargs):
        url = target_url % kwargs
        args = self.request.META.get('QUERY_STRING', '')
        if args and self.query_string:
            url = "%s?%s" % (url, args)
        return url


class AnonymousUsersOnly(View):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_anonymous():
            return HttpResponseRedirect(settings.LOGIN_REDIRECT_URL)
        else:
            return super(AnonymousUsersOnly, self).dispatch(request, *args, **kwargs)


class SignupStartView(AnonymousUsersOnly, ForwardQueryStringMixin, FormView):
    form_class = SignupStartForm
    template_name = 'authentication/phone/signup_start.html'
    verifier_lifetime = settings.PHONE_VERIFIER_LIFETIME
    operation_key = operations.SIGNUP_BY_PHONE

    def setup_success_url(self):
        if 'existing_users' in self.operation.data:
            next_url = 'signup_or_signin_by_phone'
        else:
            next_url = 'signup_by_phone_get_verifier'
        self.success_url = self.forward_query_string(reverse_lazy(next_url, kwargs={'uid': self.operation.uid}))

    def get_success_url(self):
        self.setup_success_url()
        return super(SignupStartView, self).get_success_url()

    def get_existing_users_ids(self, data):
        phone = data['phone']
        users_ids = User.objects.filter(
            userprofile__phones__phone_number=phone, userprofile__phones__is_active=True).values_list('id', flat=True)
        return users_ids

    def form_valid(self, form):
        data = form.cleaned_data

        # try to find already existing accounts
        users_ids = list(self.get_existing_users_ids(data))
        if users_ids:
            data['existing_users'] = users_ids

        op = Operation()
        op.operation_key = self.operation_key
        op.data = data
        op.date_expires = timezone.now() + timedelta(milliseconds=self.verifier_lifetime)
        op.save()
        self.operation = op
        return super(SignupStartView, self).form_valid(form)


class ToManyDispatchesMixin(object):
    query_string = True
    verifier_dispatch_count = 0
    to_many_dispatches_url = None

    def check_dispatch_count(self):
        return len(self.object.data['verifiers']) >= self.verifier_dispatch_count

    def get_to_many_dispatches_url(self, **kwargs):
        """
        Return the URL redirect to. Keyword arguments from the
        URL pattern match generating the redirect request
        are provided as kwargs to this method.
        """
        if self.to_many_dispatches_url:
            url = self.to_many_dispatches_url % kwargs
            args = self.request.META.get('QUERY_STRING', '')
            if args and self.query_string:
                url = "%s?%s" % (url, args)
            return url
        else:
            return None

    def to_many_dispatches(self, **kwargs):
        return HttpResponseRedirect(self.get_to_many_dispatches_url(**kwargs))


class SendVerifierView(AnonymousUsersOnly, SingleObjectMixin, ToManyDispatchesMixin, RedirectView):
    model = Operation
    slug_field = 'uid'
    slug_url_kwarg = 'uid'
    permanent = False
    query_string = True
    operation_key = None
    verifier_dispatch_count = settings.PHONE_VERIFIER_DISPATCH_COUNT
    verifier_length = settings.PHONE_VERIFIER_LENGTH
    verifier_symbols = settings.PHONE_VERIFIER_SYMBOLS

    def generate_verifier(self):
        return ''.join(random.choice(self.verifier_symbols) for x in range(self.verifier_length))

    def get_message(self, verifier):
        return u'Код подтверждения: %s' % verifier

    def send_verifier(self, verifier):
        phone = self.get_object().data['phone']
        # send_wvs.delay(phone, self.get_message(verifier))
        send_viber_or_sms.delay(phone, self.get_message(verifier))

    def get_queryset(self):
        return self.model.objects.filter(status='new', operation_key=self.operation_key)

    def get(self, request, *args, **kwargs):
        obj = self.object = self.get_object()

        if not 'verifiers' in obj.data:
            obj.data['verifiers'] = []

        if len(obj.data['verifiers']) == 0 or 'forced_send_verifier' in kwargs:

            # if self.check_dispatch_count():
            #     return self.to_many_dispatches()

            verifier = self.generate_verifier()
            obj.data['verifiers'].append(verifier)
            obj.save()
            self.send_verifier(verifier)
        else:
            obj.data['verifier_is_sent'] = True
            obj.save()

        return super(SendVerifierView, self).get(request, *args, **kwargs)


class SignupSendVerifierView(SendVerifierView):
    operation_key = operations.SIGNUP_BY_PHONE
    verifier_dispatch_count = settings.PHONE_VERIFIER_DISPATCH_COUNT
    to_many_dispatches_url = reverse_lazy('signup_by_phone_to_many_verifier_dispatches')

    def get_redirect_url(self, **kwargs):
        self.url = reverse_lazy('signup_by_phone_complete', kwargs={'uid': self.object.uid})
        return super(SignupSendVerifierView, self).get_redirect_url(**kwargs)

    def get_message(self, verifier):
        code_life_time = DEFAULT_OPERATION_EXPIRATION_PERIOD / 60 / 1000
        return u'Код подтверждения регистрации: %s.' % (verifier, )

    def to_many_dispatches(self):
        self.object.status = 'expired'
        self.object.save()
        return super(SignupSendVerifierView, self).to_many_dispatches()


class SignupCompleteView(AnonymousUsersOnly, SingleObjectMixin, FormView):
    model = Operation
    form_class = None
    slug_field = 'uid'
    slug_url_kwarg = 'uid'
    operation_key = None
    redirect_field_name = REDIRECT_FIELD_NAME
    success_url = settings.LOGIN_REDIRECT_URL

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super(SignupCompleteView, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super(SignupCompleteView, self).post(request, *args, **kwargs)

    def get_initial(self):
        init = super(SignupCompleteView, self).get_initial()
        init['uid'] = self.object.uid
        return init

    def get_success_url(self):
        return self.request.REQUEST.get(self.redirect_field_name, self.success_url)

    def get_queryset(self):
        return self.model.objects.filter(status='new', operation_key=self.operation_key)


class PhoneSignupCompleteView(SignupCompleteView):
    operation_key = operations.SIGNUP_BY_PHONE
    template_name = 'authentication/phone/signup_complete.html'
    form_class = SignupCompleteForm

    def get_form_kwargs(self):
        kwargs = super(PhoneSignupCompleteView, self).get_form_kwargs()
        kwargs.pop('instance', None)
        obj = self.object
        kwargs['uid'] = obj.uid
        kwargs['verifiers'] = obj.data['verifiers']
        return kwargs

    def form_valid(self, form):
        user = User()
        user.username = generate_username()
        user.first_name = self.object.data['salutation']
        password = User.objects.make_random_password()
        user.set_password(password)
        user.save()

        phone = self.object.data['phone']

        up = user.userprofile
        up.salutation = self.object.data['salutation']
        up.save()

        pn = PhoneNumber(content_object=up, phone_number=phone, is_verified=True, is_active=True, is_main=True)
        pn.save()

        self.object.status = 'done'
        self.object.save()

        # send_sms.delay(u'Ваш пароль: %s. После входа можете сменить его в настройках профиля.' % password, phone)

        user.backend = 'django.contrib.auth.backends.ModelBackend'
        login(self.request, user)

        return super(PhoneSignupCompleteView, self).form_valid(form)


class SignupOrSigninView(AnonymousUsersOnly, ForwardQueryStringMixin, DetailView):
    model = Operation
    slug_field = 'uid'
    slug_url_kwarg = 'uid'
    template_name = 'authentication/phone/signup_or_signin.html'
    query_string = True
    operation_key = operations.SIGNUP_BY_PHONE

    def get_queryset(self):
        return self.model.objects.filter(status='new', operation_key=self.operation_key)

    def get_context_data(self, **kwargs):
        kwargs['users'] = User.objects.filter(id__in=self.object.data['existing_users'])
        return super(SignupOrSigninView, self).get_context_data(**kwargs)


class SigninView(AnonymousUsersOnly, ForwardQueryStringMixin, FormView):
    form_class = SigninForm
    template_name = 'authentication/phone/signin.html'
    success_url = settings.LOGIN_REDIRECT_URL
    redirect_field_name = REDIRECT_FIELD_NAME

    def get_initial(self):
        initial = super(SigninView, self).get_initial()
        phone = self.request.GET.get('phone', None)
        if phone:
            initial['phone'] = phone
        return initial

    def form_valid(self, form):
        login(self.request, form.get_user())
        return super(SigninView, self).form_valid(form)

    def get_success_url(self):
        return self.request.REQUEST.get(self.redirect_field_name, self.success_url)


class SigninBySmsStartView(AnonymousUsersOnly, ForwardQueryStringMixin, FormView):
    form_class = SigninBySmsStartForm
    template_name = 'authentication/phone/signin_by_sms.html'
    verifier_lifetime = settings.SIGNIN_BRUTE_FORCE_PROTECTION_PAUSE
    operation_key = operations.SIGNIN_BY_SMS

    def get_success_url(self):
        self.success_url = self.forward_query_string(
            reverse_lazy('signin_by_sms_get_verifier', kwargs={'uid': self.operation.uid}))
        return super(SigninBySmsStartView, self).get_success_url()

    def form_valid(self, form):
        data = form.cleaned_data

        op_request, _ = Operation.objects.get_or_create(
            operation_key=self.operation_key,
            user=form.get_user(),
            status='new',
            defaults={
                'data': data,
                'date_expires': timezone.now() + timedelta(milliseconds=self.verifier_lifetime)
            }
        )
        self.operation = op_request
        return super(SigninBySmsStartView, self).form_valid(form)

    def render_to_response(self, context, **response_kwargs):
        context['query_string'] = self.request.META['QUERY_STRING']
        return super(SigninBySmsStartView, self).render_to_response(context, **response_kwargs)


class SigninBySmsSendVerifierView(SendVerifierView):
    operation_key = operations.SIGNIN_BY_SMS
    verifier_dispatch_count = settings.SIGNIN_ATTEMPTS_COUNT
    to_many_dispatches_url = reverse_lazy('signin_by_sms_to_many_verifier_dispatches')

    def get_redirect_url(self, **kwargs):
        self.url = reverse_lazy('signin_by_sms_complete', kwargs={'uid': self.object.uid})
        return super(SigninBySmsSendVerifierView, self).get_redirect_url(**kwargs)

    def get_message(self, verifier):
        return u'Код для входа в систему: %s' % verifier


class SigninBySmsResendVerifierView(SigninBySmsSendVerifierView):

    def get(self, request, *args, **kwargs):
        kwargs['forced_send_verifier'] = True
        return super(SigninBySmsResendVerifierView, self).get(request, *args, **kwargs)


class SigninBySmsCompleteView(AnonymousUsersOnly, SingleObjectMixin, ToManyDispatchesMixin, FormView):
    form_class = SigninBySmsCompleteForm
    template_name = 'authentication/phone/signin_by_sms_complete.html'
    success_url = settings.LOGIN_REDIRECT_URL
    model = Operation
    slug_field = 'uid'
    slug_url_kwarg = 'uid'
    operation_key = operations.SIGNIN_BY_SMS
    redirect_field_name = REDIRECT_FIELD_NAME
    verifier_dispatch_count = settings.SIGNIN_ATTEMPTS_COUNT
    to_many_dispatches_url = reverse_lazy('signin_by_sms_to_many_verifier_dispatches')

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        # if self.check_dispatch_count():
        #     return self.to_many_dispatches()
        return super(SigninBySmsCompleteView, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        # if self.check_dispatch_count():
        #     return self.to_many_dispatches()
        return super(SigninBySmsCompleteView, self).post(request, *args, **kwargs)

    def get_initial(self):
        init = super(SigninBySmsCompleteView, self).get_initial()
        init['phone'] = self.object.data.get('phone', '')
        return init

    def get_success_url(self):
        return self.request.REQUEST.get(self.redirect_field_name, self.success_url)

    def get_queryset(self):
        return self.model.objects.filter(status='new', operation_key=self.operation_key)

    def form_valid(self, form):
        self.object.status = 'done'
        self.object.save()

        # Отправляем пользователя на страницу заполнения профиля, если он у него пустой. Иначе авторизуем пользователя.
        # user = form.get_user()
        # if not user.userprofile.first_name:
        #     uid = self.object.uid
        #     query_string = self.request.META['QUERY_STRING']
        #     self.success_url = '/auth/phone/fill_user_profile/%s/?%s' % (uid, query_string)
        #     self.redirect_field_name = None
        # else:
        #     login(self.request, form.get_user())

        login(self.request, form.get_user())

        return super(SigninBySmsCompleteView, self).form_valid(form)

    def render_to_response(self, context, **response_kwargs):
        context['phone'] = self.object.data.get('phone', '')
        context['verifier_is_sent'] = self.object.data.get('verifier_is_sent', False)
        context['uid'] = self.object.uid
        context['query_string'] = self.request.META['QUERY_STRING']
        return super(SigninBySmsCompleteView, self).render_to_response(context, **response_kwargs)


class FillUserProfileView(FormView):
    form_class = FillUserProfileForm
    template_name = 'authentication/phone/fill_user_profile.html'
    success_url = settings.LOGIN_REDIRECT_URL
    redirect_field_name = REDIRECT_FIELD_NAME

    def get(self, request, *args, **kwargs):
        operation = Operation.objects.filter(uid=kwargs['uid'], status='done')
        if not operation:
            return HttpResponseRedirect('/auth/phone/signin/sms/?%s' % self.request.META['QUERY_STRING'])
        return super(FillUserProfileView, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        operation = Operation.objects.filter(uid=kwargs['uid'], status='done')
        if not operation:
            return HttpResponseRedirect('/auth/phone/signin/sms/?%s' % self.request.META['QUERY_STRING'])
        self.operation = operation[0]
        return super(FillUserProfileView, self).post(request, *args, **kwargs)

    def get_success_url(self):
        return self.request.REQUEST.get(self.redirect_field_name, self.success_url)

    def form_valid(self, form):
        data = form.cleaned_data
        user = User.objects.get(id=self.operation.user.id)

        user.first_name = data['first_name']
        user.save()
        user.userprofile.first_name = data['first_name']
        user.userprofile.birth_date = data['birth_date']
        user.userprofile.sex = data['sex'] if data['sex'] else user.userprofile.sex
        user.userprofile.smoking = data['smoking'] if data['smoking'] else user.userprofile.smoking
        user.userprofile.save()

        user.backend = 'apps.authentication.phone.backends.SmsBackend'
        login(self.request, user)

        return super(FillUserProfileView, self).form_valid(form)


class SignupTooManyVerifierDispatches(TemplateView):
    template_name = 'authentication/phone/signup_to_many_dispatches.html'


class SigninTooManyVerifierDispatches(TemplateView):
    template_name = 'authentication/phone/signin_to_many_dispatches.html'


class SigninBySmsTooManyVerifierDispatches(TemplateView):
    template_name = 'authentication/phone/signin_by_sms_to_many_dispatches.html'