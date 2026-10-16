import uuid

from django import forms
from django.db.models import Q

from .models import UsageLog


class RequestLogFilters(forms.Form):
    q = forms.CharField(max_length=200, required=False, label='Endpoint or key name')
    request_id = forms.UUIDField(required=False, label='Request ID')
    status = forms.ChoiceField(required=False, choices=[('', 'All statuses'), ('success', 'Success (2xx–3xx)'), ('client_error', 'Client errors (4xx)'), ('server_error', 'Server errors (5xx)'), ('pending', 'Pending')])
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={'type':'date'}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={'type':'date'}))

    def clean(self):
        data = super().clean()
        if data.get('date_from') and data.get('date_to') and data['date_from'] > data['date_to']:
            raise forms.ValidationError('Start date must be before or equal to end date.')
        return data


def filtered_request_logs(request):
    form = RequestLogFilters(request.GET)
    logs = UsageLog.objects.filter(api_key__user=request.user).select_related('api_key').order_by('-created_at', '-id')
    if not form.is_valid():
        return form, logs.none()
    data = form.cleaned_data
    if data['request_id']:
        logs = logs.filter(request_id=data['request_id'])
    if data['q']:
        query = Q(endpoint__icontains=data['q']) | Q(api_key__name__icontains=data['q'])
        try:
            query |= Q(request_id=uuid.UUID(data['q']))
        except ValueError:
            pass
        logs = logs.filter(query)
    if data['status'] == 'success':
        logs = logs.filter(status_code__gte=200, status_code__lt=400)
    elif data['status'] == 'client_error':
        logs = logs.filter(status_code__gte=400, status_code__lt=500)
    elif data['status'] == 'server_error':
        logs = logs.filter(status_code__gte=500)
    elif data['status'] == 'pending':
        logs = logs.filter(status_code__isnull=True)
    if data['date_from']:
        logs = logs.filter(date__gte=data['date_from'])
    if data['date_to']:
        logs = logs.filter(date__lte=data['date_to'])
    return form, logs
