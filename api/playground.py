from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView


class PlaygroundPage(LoginRequiredMixin, TemplateView):
    template_name = 'playground.html'

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        response['Cache-Control'] = 'private, no-store'
        return response
