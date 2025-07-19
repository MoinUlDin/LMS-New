
from django.conf import settings

class CrossOriginResourcePolicyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # if it’s a static *or* media URL
        if request.path.startswith(settings.STATIC_URL) or \
           request.path.startswith(settings.MEDIA_URL):
            response['Cross-Origin-Resource-Policy'] = 'same-site'
        return response