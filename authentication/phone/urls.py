# -*- coding: utf-8 -*-
from django.conf.urls import patterns, url
from apps.authentication.phone.views import SignupStartView, SignupSendVerifierView, SigninView, \
    SignupOrSigninView, SigninBySmsStartView, SigninBySmsCompleteView, SigninBySmsSendVerifierView,\
    SignupTooManyVerifierDispatches, SigninTooManyVerifierDispatches, SigninBySmsTooManyVerifierDispatches,\
    PhoneSignupCompleteView, FillUserProfileView, SigninBySmsResendVerifierView

urlpatterns = patterns(
    '',
    url(r'^signup/$', SignupStartView.as_view(), name='signup_by_phone'),
    url(r'^signup/(?P<uid>[\w\d-]+)/verifier/$', SignupSendVerifierView.as_view(), name='signup_by_phone_get_verifier'),
    url(r'^signup/(?P<uid>[\w\d-]+)/complete/$', PhoneSignupCompleteView.as_view(), name='signup_by_phone_complete'),
    url(r'^signup/to-many-verifier-dispatches/$', SignupTooManyVerifierDispatches.as_view(),
        name='signup_by_phone_to_many_verifier_dispatches'),

    url(r'signup-or-signin/(?P<uid>[\w\d-]+)/$', SignupOrSigninView.as_view(), name='signup_or_signin_by_phone'),

    url(r'^signin/$', SigninView.as_view(), name='signin_by_phone'),
    url(r'^signin/to-many-verifier-dispatches/$', SigninTooManyVerifierDispatches.as_view(),
        name='signin_by_phone_to_many_verifier_dispatches'),
    url(r'^signin/sms/$', SigninBySmsStartView.as_view(), name='signin_by_sms'),
    url(r'^signin/sms/(?P<uid>[\w\d-]+)/verifier/$', SigninBySmsSendVerifierView.as_view(), name='signin_by_sms_get_verifier'),
    url(r'^signin/sms/(?P<uid>[\w\d-]+)/resend_verifier/$', SigninBySmsResendVerifierView.as_view(), name='signin_by_sms_resend_verifier'),
    url(r'^signin/sms/(?P<uid>[\w\d-]+)/complete/$', SigninBySmsCompleteView.as_view(), name='signin_by_sms_complete'),
    url(r'^signin/sms/to-many-verifier-dispatches/$', SigninBySmsTooManyVerifierDispatches.as_view(),
        name='signin_by_sms_to_many_verifier_dispatches'),

    url(r'^fill_user_profile/(?P<uid>[\w\d-]+)/$', FillUserProfileView.as_view(), name='fill_user_profile'),
)