# -*- coding: utf-8 -*-
from datetime import timedelta, date
from libs.admin import admin
from django.contrib.admin import SimpleListFilter
from django.contrib.auth.admin import User, UserAdmin
from django.contrib.staticfiles.storage import staticfiles_storage
from django.contrib.auth.models import Group
from django.core.files.storage import default_storage
from django.db.models import Q
from django.utils import timezone
from relationships.admin import RelationshipInline
from apps.accounts.models import UserProfile, AppProfile


class ProfileInline(admin.StackedInline):
    model = UserProfile
    fk_name = 'user'
    max_num = 1
    readonly_fields = ['phone', 'create_user_link']

    def phone(self, obj):
        return obj.get_phone()
    phone.short_description = u'Номер телефона'

    def create_user_link(self, obj):
        return u'<h1><a href="/create_user/">СОЗДАТЬ НОВОГО ПОЛЬЗОВАТЕЛЯ</a></h1>'
    create_user_link.short_description = u''
    create_user_link.allow_tags = True


class AppListFilter(SimpleListFilter):
    title = u'приложение'
    parameter_name = u'app'

    def lookups(self, request, model_admin):
        return (
            ('mobile', u'Android App'),
            ('web', u'Web App'),
        )

    def queryset(self, request, queryset):
        val = self.value()
        if val == 'mobile':
            queryset = queryset.exclude(username__istartswith='1@')
        elif val == 'web':
            queryset = queryset.filter(username__istartswith='1@')
        return queryset


class AgeGroupListFilter(SimpleListFilter):
    title = u'возрастная группа'
    parameter_name = u'age'

    def lookups(self, request, model_admin):
        return (
            ('null', u'не указан'),
            ('-16', u'до 16'),
            ('17-21', u'от 17 до 21'),
            ('22-27', u'от 22 до 27'),
            ('28-32', u'от 28 до 32'),
            ('33-38', u'от 33 до 38'),
            ('39-', u'старше 39'),
        )

    def queryset(self, request, queryset):
        val = self.value()
        if val == 'null':
            return queryset.filter(userprofile__birth_date=None)
        elif val:
            min_age, max_age = self.value().split('-')
            str_to_age = lambda s: int(s) if s.isdigit() else None
            min_age = str_to_age(min_age)
            max_age = str_to_age(max_age)
            now = timezone.now()
            q = None
            if max_age:
                date_start = date(now.year - max_age, now.month, now.day) + timedelta(days=1)
                q = Q(userprofile__birth_date__gt=date_start)
            if min_age:
                date_end = date(now.year - min_age, now.month, now.day)
                if not q:
                    q = Q(userprofile__birth_date__lte=date_end)
                else:
                    q = q & Q(userprofile__birth_date__lte=date_end)
            if q:
                queryset = queryset.exclude(userprofile__birth_date=None).filter(q)
            return queryset


class UserGroupListFilter(admin.SimpleListFilter):
    title = u'группа пользователей'
    parameter_name = u'user group'

    def lookups(self, request, model_admin):
        return (
            ('scania', u'Скания'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'scania':
            group = Group.objects.filter(name='scania')
            group_id = group[0].id if group else 0
            return queryset.filter(groups__in=[group_id])
        else:
            return queryset


class UserProfileAdmin(UserAdmin):
    inlines = [ProfileInline, RelationshipInline]
    list_display = ('username', 'first_name', 'last_name', 'phone', 'avatar', 'contact_info', 'dates')
    list_filter = ('userprofile__sex', AgeGroupListFilter, AppListFilter, UserGroupListFilter)
    date_hierarchy = 'date_joined'
    search_fields = ['username', 'first_name', 'last_name']
    readonly_fields = ['phone']

    def avatar(self, obj):
        avatars = list(obj.avatars.filter(primary=True))
        img_url = staticfiles_storage.url('avatars/default_normal.png')
        if avatars:
            img_name = avatars[0].image.name
            img_path, ext = img_name.rsplit('.', 1)
            normal_img_name = u'%s_normal.%s' % (img_path, ext)
            if default_storage.exists(normal_img_name):
                img_url = default_storage.url(normal_img_name)
            else:
                img_url = default_storage.url(img_name)
        return u'<img src="%s" style="width:64px;">' % img_url
    avatar.allow_tags = True

    def contact_info(self, obj):
        res = u'ФИ: %s %s' % (obj.last_name or '?', obj.first_name or '?')
        res += u'<br/>Обращение: %s' % obj.userprofile.salutation or '?'
        res += u'<br/>тел.: %s' % obj.userprofile.phone or '?'
        res += u'<br/>Маршрутов: %s' % obj.userprofile.routes_count
        if obj.username.startswith('1@'):
            _, vk_id = obj.username.rsplit('@', 1)
            res += u'<br/>VK: <a href="https://vk.com/id%(vk_id)s">https://vk.com/id%(vk_id)s</a>' % {'vk_id': vk_id}
        return res
    contact_info.allow_tags = True

    def dates(self, obj):
        tmplt = u'''
        Reg: %(date_joined)s
        <br/>Seen: %(last_login)s
        '''
        date_format = '%Y-%m-%d %H:%M'
        return tmplt % {'date_joined': obj.date_joined.strftime(date_format), 'last_login': obj.last_login.strftime(date_format)}
    dates.allow_tags = True

    def phone(self, obj):
        return obj.userprofile.get_phone().phone_number
    phone.short_description = u'Номер телефона'


class AppProfileAdmin(admin.ModelAdmin):
    pass


class RealUserProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'user_id', 'first_name', 'last_name', 'phone', 'birth_date', 'last_activity',
                    'last_client_data')
    search_fields = ('first_name', 'last_name')

    def phone(self, obj):
        return obj.get_phone().phone_number
    phone.short_description = u'Номер телефона'

    def user_id(self, obj):
        return obj.user_id


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass
admin.site.register(User, UserProfileAdmin)
admin.site.register(AppProfile, AppProfileAdmin)
admin.site.register(UserProfile, RealUserProfileAdmin)