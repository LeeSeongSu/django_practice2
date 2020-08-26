import json

from django import forms
from django.template.loader import render_to_string
from django.utils.encoding import smart_text
from django.utils.safestring import mark_safe

from config import settings
from .models import Order


class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ('name', 'amount')
        widgets = {
            'name': forms.TextInput(attrs={'readonly': 'readonly'}),
            'amount': forms.TextInput(attrs={'readonly': 'readonly'}),
        }


class PayForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ('imp_uid',)

    def as_iamport(self):
        # Form 의 Hidden 필드 위젯
        # 1. Form 을 통해 들어오는 imp_uid 를 smart_text 함수로 str 로 변환
        # 2. 템플릿 태그를 사용하여 for 문으로 출력하도록 mark_safe 를 사용
        hidden_fields = mark_safe(''.join(smart_text(field) for field in self.hidden_fields()))

        # IMP.request_pay 의 인자로 넘길 인자 목록
        fields = {
            'merchant_uid': str(self.instance.merchant_uid),    # uuid4(32자리의 str, 하이픈 제외)
            'name': self.instance.name,
            'amount': self.instance.amount,
        }

        return hidden_fields + render_to_string('shop/_iamport.html', {
            'json_fields': mark_safe(json.dumps(fields, ensure_ascii=False)),
            'iamport_shop_id': settings.IAMPORT_SHOP_ID,   # 각자의 상점 아이디를 입력
        })

    def save(self):
        order = super().save(commit=False)
        order.status = 'paid'   # 아임포트 API 를 통한 확인 후에 변경
        # Order 모델에 정의한 update()
        order.update()

        return order
