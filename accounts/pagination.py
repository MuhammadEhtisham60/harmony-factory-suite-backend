"""
Standardized Pagination classes conforming to the API specification.
"""

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        total_pages = self.page.paginator.num_pages if self.page else 1
        current_page = self.page.number if self.page else 1
        page_size = self.get_page_size(self.request) or self.page_size

        return Response({
            'success': True,
            'count': self.page.paginator.count if self.page else len(data),
            'totalPages': total_pages,
            'currentPage': current_page,
            'pageSize': page_size,
            'results': data
        })


class ActivityLogPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        total_pages = self.page.paginator.num_pages if self.page else 1
        current_page = self.page.number if self.page else 1
        page_size = self.get_page_size(self.request) or self.page_size

        return Response({
            'success': True,
            'count': self.page.paginator.count if self.page else len(data),
            'totalPages': total_pages,
            'currentPage': current_page,
            'pageSize': page_size,
            'results': data
        })
