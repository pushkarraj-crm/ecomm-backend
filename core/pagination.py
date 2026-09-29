from django.conf import settings
from rest_framework.pagination import PageNumberPagination


class ProductPagination(PageNumberPagination):
    page_size = settings.API_PAGE_SIZE
    page_size_query_param = 'page_size'
    max_page_size = settings.API_MAX_PAGE_SIZE

    def get_page_size(self, request):
        requested_size = request.query_params.get(self.page_size_query_param)
        if requested_size is None:
            return self.page_size
        try:
            requested_size = int(requested_size)
        except (TypeError, ValueError):
            return self.page_size
        if requested_size < 1:
            return self.page_size
        return min(requested_size, self.max_page_size)
