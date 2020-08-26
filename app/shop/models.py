from datetime import datetime
from uuid import uuid4

import pytz
from django.conf import settings
from django.contrib.humanize.templatetags.humanize import intcomma
from django.db import models
from django.http import Http404
from django.utils.safestring import mark_safe
from iamport import Iamport
from jsonfield import JSONField


def named_property(name):
    def wrap(fn):
        fn.short_description = name
        return property(fn)
    return wrap


def timestamp_to_datetime(timestamp):
    if timestamp:
        tz = pytz.timezone(settings.TIME_ZONE)
        return datetime.utcfromtimestamp(timestamp).replace(tzinfo=tz)
    return None


class Item(models.Model):
    name = models.CharField(max_length=100)
    desc = models.TextField(blank=True)
    amount = models.PositiveIntegerField()
    photo = models.ImageField()
    is_public = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Order(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    # 32개의 16진수 숫자로 만들어지는 UUID 를 생성하여 주문에 대한 고유한 값을 가짐
    merchant_uid = models.UUIDField(default=uuid4, editable=False)
    # imp_uid 는 iamport 에서 가입하면 발급받는 가맹점 식별코드로 imp+<int>의 값을 가짐
    imp_uid = models.CharField(max_length=100, blank=True)
    name = models.CharField(max_length=100, verbose_name='상품명')
    amount = models.PositiveIntegerField(verbose_name='결제금액')
    # 결제 상태를 총 4개의 상태 코드로 설정하고 기본값은 '미결제'로 설정
    status = models.CharField(
        max_length=9,
        choices=(
            ('ready', '미결제'),
            ('paid', '결제완료'),
            ('cancelled', '결제취소'),
            ('failed', '결제실패'),
        ),
        default='ready',
        # status 필드에 index 를 추가하기 때문에 DB 에서 status 필드에
        # 빠르게 접근하여 조회가 가능
        db_index=True
    )
    meta = JSONField(blank=True, default={})
    created_at = models.TimeField(auto_now_add=True)
    updated_at = models.TimeField(auto_now=True)

    # def is_ready(self):
    #     return self.status == 'ready'
    # is_ready = property(is_ready)

    # 위의 is_ready 메서드를 lambda 식으로 아래와 같이 작성
    is_ready = property(lambda self: self.status == 'ready')
    is_paid = property(lambda self: self.status == 'paid')
    # 결제 예정 금액(self.amount)와 Iamport 의 실제 결제 금액(self.meta.get('amount')) 이 같다면 처리
    is_paid_ok = property(lambda self: self.status == 'paid' and self.amount == self.meta.get('amount'))
    is_cancelled = property(lambda self: self.status == 'cancelled')
    is_failed = property(lambda self: self.status == 'failed')

    # @named_property
    # def receipt_url(self):
    #     return self.meta.get('receipt_url')
    # receipt_url.short_description = '영수증'

    # 위의 receipt_url 메서드를 lambda 식으로 아래와 같이 작성
    receipt_url = named_property('영수증')(lambda self: self.meta.get('receipt_url'))
    cancel_reason = named_property('취소이유')(lambda self: self.meta.get('cancel_reason'))
    fail_reason = named_property('실패이유')(lambda self: self.meta.get('fail_reason'))

    paid_at = named_property('결제일시')(lambda self: timestamp_to_datetime(self.meta.get('paid_at')))
    failed_at = named_property('실패일시')(lambda self: timestamp_to_datetime(self.meta.get('failed_at')))
    cancelled_at = named_property('취소일시')(lambda self: timestamp_to_datetime(self.meta.get('cancelled_at')))

    class Meta:
        ordering = ['-id']

    @property
    def api(self):
        return Iamport(settings.IAMPORT_API_KEY, settings.IAMPORT_SECRET_KEY)

    @named_property('결제금액')
    def amount_html(self):
        return mark_safe('<div style="float: right;">{0}</div>'.format(intcomma(self.amount)))

    # def amount_html(self):
    #     """
    #     @named_property 를 사용하지 않은 코딩
    #     :return:
    #     """
    #     return mark_safe('<div style="float: right;">{0}</div>'.format(intcomma(self.amount)))
    # amount_html.short_description = '결제금액'
    # amount_html = property(amount_html)

    @named_property('처리결과')
    def status_html(self):
        cls, text_color = '', ''
        help_text = ''
        if self.is_ready:
            cls, text_color = 'fa fa-shopping-cart', '#ccc'
        elif self.is_paid_ok:
            cls, text_color = 'fa fa-check-circle', 'green'
        elif self.is_cancelled:
            cls, text_color = 'fa fa-times', 'gray'
            help_text = self.is_cancelled
        elif self.is_failed:
            cls, text_color = 'fa fa-ban', 'red'
            help_text = self.fail_reason
        html = '''
            <span style="color: {text_color};" title="this is title">
            <i class="{class_names}"></i>
            {label}
            </span>'''.format(class_names=cls, text_color=text_color, label=self.get_status_display())
        if help_text:
            html += '<br/>' + help_text
        return mark_safe(html)

    @named_property('영수증 링크')
    def receipt_link(self):
        if self.is_paid_ok and self.receipt_url:
            return mark_safe('<a href="{0}" target:"_blank">영수증</a>'.format(self.receipt_url))

    def update(self, commit=False, meta=None):
        # 정상적인 접근으로 imp_uid 가 있으면
        if self.imp_uid:
            try:
                self.meta = meta or self.api.find(imp_uid=self.imp_uid)
            except Iamport.HttpError:
                raise Http404('Not found {}'.format(self.imp_uid))
            # assert 문은 해당 코드가 참이면 코드를 수행하고
            # 아닐 경우에는 AssertionError (선택사항) 을 일으킴
            assert str(self.merchant_uid) == self.meta['merchant_uid']
        if commit:
            self.save()

    def cancel(self, reason=None, commit=True):
        '결제내역 취소'
        try:
            meta = self.api.cancel(reason, imp_uid=self.imp_uid)
            assert str(self.merchant_uid) == self.meta['merchant_uid']
            self.update(commit=commit, meta=meta)
        # 취소 시 오류 예외 처리(이미 취소된 결제는 에러가 발생)
        except Iamport.ResponseError as e:
            self.update(commit=commit)
        if commit:
            self.save()
