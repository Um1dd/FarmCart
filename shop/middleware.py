from django.utils import translation

class StoreLanguageMiddleware:
    """Apply the storefront language to Django's validation and admin messages too."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        lang = request.session.get('lang', 'az')
        with translation.override(lang):
            request.LANGUAGE_CODE = lang
            response = self.get_response(request)
            response.headers.setdefault('Content-Language', lang)
            return response
