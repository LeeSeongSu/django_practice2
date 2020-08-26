from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView

from .models import Item, Order
from .forms import OrderForm, PayForm


index = ListView.as_view(model=Item,
                         queryset=Item.objects.filter(
                             is_public=True,
                         ))


class ItemListView(ListView):
    model = Item
    queryset = Item.objects.filter(is_public=True)

    def get_queryset(self):
        self.q = self.request.GET.get('q', '')

        qs = super().get_queryset()
        if self.q:
            qs = qs.filter(name__icontaines=self.q)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['q'] = self.q
        return context


@login_required
def order_new(request, item_id):
    item = get_object_or_404(Item, pk=item_id)
    order = Order.objects.create(user=request.user, item=item, name=item.name, amount=item.amount)
    return redirect('shop:order_pay', item_id, str(order.merchant_uid))


@login_required
def order_pay(request, item_id, merchant_uid):
    order = get_object_or_404(Order, user=request.user, merchant_uid=merchant_uid, status='ready')
    if request.method == 'POST':
        form = PayForm(request.POST, instance=order)
        if form.is_valid():
            form.save()

            return redirect('accounts:profile')
    else:
        form = PayForm(instance=order)

    return render(request, 'shop/pay_form.html', {
        'form': form,
    })
