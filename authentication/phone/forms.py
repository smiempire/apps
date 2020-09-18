# -*- coding: utf-8 -*-
from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.forms import HiddenInput, extras
from django.forms.widgets import TextInput
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext, ugettext_lazy as _
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Field, Layout

import settings
from apps.contacts.models import PhoneNumber
from apps.accounts.models import create_account
from libs.utils import get_last_years
from libs.phones import format_phone


class CustomTelephoneInput(TextInput):
    input_type = 'tel'


class CrispyFormMixin(object):
    def __init__(self, *args, **kwargs):
        super(CrispyFormMixin, self).__init__(*args, **kwargs)
        self.helper = FormHelper()


class SignupStartForm(CrispyFormMixin, forms.Form):
    salutation = forms.CharField(label=u'Имя', max_length=255,
                                 widget=forms.TextInput(attrs={'placeholder': u'Укажите имя'}))
    # phone = forms.CharField(label=u'Телефон', max_length=50,
    #                         widget=forms.TextInput(attrs={'placeholder': u'+79876543210'}))
    phone = forms.CharField(label=u'Телефон', max_length=50,
                            widget=CustomTelephoneInput(attrs={
                                'placeholder': u'+79876543210',
                                'value': u'+7',
                            }))

    def __init__(self, *args, **kwargs):
        super(SignupStartForm, self).__init__(*args, **kwargs)
        self.helper.form_method = 'POST'
        self.helper.add_input(Submit('submit', u'Получить проверочный код'))

    def clean_phone(self):
        phone = self.cleaned_data['phone']
        phone = PhoneNumber.format(phone)
        return phone


class SignupCompleteForm(CrispyFormMixin, forms.Form):
    uid = forms.SlugField(label=u'Ключ операции', widget=HiddenInput())
    verifiers = forms.CharField(label=u'Код', min_length=settings.PHONE_VERIFIER_LENGTH,
                               max_length=settings.PHONE_VERIFIER_LENGTH,
                               widget=forms.TextInput(attrs={'placeholder': u'Введите код из SMS'}))

    def __init__(self, uid, verifiers=None, *args, **kwargs):
        super(SignupCompleteForm, self).__init__(*args, **kwargs)
        self.uid = uid
        self.verifiers = verifiers
        self.helper.form_method = 'POST'
        self.helper.add_input(Submit('submit', u'Готово'))

    def clean_uid(self):
        if not self.uid or self.cleaned_data['uid'] != self.uid:
            raise forms.ValidationError(u'Неверный идентификатор операции.')
        return self.cleaned_data['uid']

    def clean_verifier(self):
        if self.verifiers not in self.cleaned_data['verifiers']:
            raise forms.ValidationError(u'Неверный код подтверждения.')
        return self.cleaned_data['verifiers']


class PhoneNumberForm(forms.Form):
    # phone = forms.CharField(label=u'Телефон', max_length=50,
    #                         widget=forms.TextInput(attrs={'placeholder': u'+79876543210'}))
    phone = forms.CharField(label=u'Укажите свой номер телефона', max_length=50,
                            widget=CustomTelephoneInput(attrs={
                                'placeholder': u'+7(921)000-00-00',
                                'value': u'+7',
                            }))

    def clean_phone(self):
        phone = self.cleaned_data['phone']
        phone = PhoneNumber.format(phone)
        return phone


class AuthFormMixin(object):
    def __init__(self, request=None, *args, **kwargs):
        super(AuthFormMixin, self).__init__(*args, **kwargs)
        self.error_messages = {
            'invalid_login': _("Please enter a correct username and password. "
                               "Note that both fields are case-sensitive."),
            'no_cookies': _("Your Web browser doesn't appear to have cookies "
                            "enabled. Cookies are required for logging in."),
            'inactive': _("This account is inactive."),
        }
        self.request = request
        self.user_cache = None

    def clean(self):
        cleaned_data = super(AuthFormMixin, self).clean()
        self.authenticate(**cleaned_data)
        return cleaned_data

    def authenticate(self, **kwargs):
        self.user_cache = authenticate(**kwargs)
        if self.user_cache is None:
            raise forms.ValidationError(self.error_messages['invalid_login'])
        elif not self.user_cache.is_active:
            raise forms.ValidationError(self.error_messages['inactive'])
        self.check_for_test_cookie()

    def check_for_test_cookie(self):
        if self.request and not self.request.session.test_cookie_worked():
            raise forms.ValidationError(self.error_messages['no_cookies'])

    def get_user_id(self):
        if self.user_cache:
            return self.user_cache.id
        return None

    def get_user(self):
        return self.user_cache


class SigninForm(CrispyFormMixin, AuthFormMixin, PhoneNumberForm):
    password = forms.CharField(label=u'Пароль', max_length=255,
                               widget=forms.PasswordInput())

    def __init__(self, request=None, *args, **kwargs):
        super(SigninForm, self).__init__(*args, **kwargs)
        self.error_messages['invalid_login'] = _(u"Пожалуйста введите корректный номер телефона и пароль.")
        self.helper.form_method = 'POST'
        self.helper.add_input(Submit('submit', u'Войти'))


class SigninBySmsStartForm(CrispyFormMixin, PhoneNumberForm):
    def __init__(self, *args, **kwargs):
        super(SigninBySmsStartForm, self).__init__(*args, **kwargs)
        self.user_cache = None
        self.error_messages = {
            # 'invalid_login': mark_safe(_(u'Введённый номер телефона не зарегистрирован.'
            #                              u' <a href="%s">Зарегистрироваться?</a>') % reverse('signup_by_phone')),
            'inactive': u'This account is inactive.',
            'invalid_phone': u'Некорректный номер телефона. '
                             u'Необходимо ввести номер в международном формате, например +7(921)000-00-00.',
        }
        self.helper.form_method = 'POST'
        self.helper.add_input(Submit('submit', u'Продолжить'))

    def clean(self):
        cleaned_data = super(SigninBySmsStartForm, self).clean()
        phone = format_phone(cleaned_data.get('phone'))
        if not phone:
            raise forms.ValidationError(self.error_messages['invalid_phone'])
        try:
            self.user_cache = User.objects.get(
                userprofile__phones__phone_number=phone,
                userprofile__phones__is_active=True,
                userprofile__phones__is_verified=True
            )
        except User.DoesNotExist:
            self.user_cache = create_account(phone)
        if not self.user_cache.is_active:
            raise forms.ValidationError(self.error_messages['inactive'])
        return cleaned_data

    def get_user_id(self):
        if self.user_cache:
            return self.user_cache.id
        return None

    def get_user(self):
        return self.user_cache


class SigninBySmsCompleteForm(CrispyFormMixin, AuthFormMixin, PhoneNumberForm):
    phone = forms.CharField(max_length=50, widget=forms.HiddenInput)
    password = forms.CharField(label=u'Код', min_length=settings.PHONE_VERIFIER_LENGTH,
                               max_length=settings.PHONE_VERIFIER_LENGTH, widget=CustomTelephoneInput)

    def __init__(self, *args, **kwargs):
        super(SigninBySmsCompleteForm, self).__init__(*args, **kwargs)
        self.error_messages['invalid_login'] = _(u"Пожалуйста, введите правильный временный пароль.")
        self.helper.form_method = 'POST'
        self.helper.add_input(Submit('submit', u'Готово'))


SEX_CHOICES = (
    (2, u'Мужской'),
    (1, u'Женский'),
)

SMOKING_CHOICES = (
    (False, u'Да'),
    (True, u'Нет'),
)


class FillUserProfileForm(CrispyFormMixin, forms.Form):
    first_name = forms.CharField(label=u'Имя', max_length=255)
    birth_date = forms.DateField(label=u'Дата рождения', required=False, widget=extras.SelectDateWidget(years=get_last_years(100)))
    sex = forms.ChoiceField(label=u'Пол', choices=SEX_CHOICES, widget=forms.RadioSelect, required=False)
    smoking = forms.ChoiceField(label=u'Курение в машине', choices=SMOKING_CHOICES, widget=forms.RadioSelect, required=False)

    def __init__(self, *args, **kwargs):
        super(FillUserProfileForm, self).__init__(*args, **kwargs)
        self.helper.form_method = 'POST'
        self.helper.add_input(Submit('submit', u'Готово'))