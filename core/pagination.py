from rest_framework.pagination import CursorPagination, PageNumberPagination


class DeliveryFeedPagination(CursorPagination):
    ordering = "-id"
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100


class StandardPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200