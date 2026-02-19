from django.urls import path
from .views import (
    ProductListView,
    ProductDetailView,
    ProductExportView,
    UserRegisterView,
    UserLoginView,
    ContactListCreateView,
    ContactDetailView,
    BasketView,
    OrderListCreateView,
    OrderDetailView,
    PartnerStateView,
    PartnerOrdersView,
    PartnerImportView,
    AdminImportTaskView,
)


urlpatterns = [
    path("products/", ProductListView.as_view(), name="product-list"),
    path("products/<int:pk>/", ProductDetailView.as_view(), name="product-detail"),
    path("products/export/", ProductExportView.as_view(), name="product-export"),

    path("users/register/", UserRegisterView.as_view(), name="user-register"),
    path("users/login/", UserLoginView.as_view(), name="user-login"),

    path("contacts/", ContactListCreateView.as_view(), name="contact-list-create"),
    path("contacts/<int:pk>/", ContactDetailView.as_view(), name="contact-detail"),

    path("basket/", BasketView.as_view(), name="basket"),

    path("orders/", OrderListCreateView.as_view(), name="order-list-create"),
    path("orders/<int:pk>/", OrderDetailView.as_view(), name="order-detail"),

    path("partner/state/", PartnerStateView.as_view(), name="partner-state"),
    path("partner/orders/", PartnerOrdersView.as_view(), name="partner-orders"),
    path("partner/import/", PartnerImportView.as_view(), name="partner-import"),
    path("admin/do-import/", AdminImportTaskView.as_view(), name="admin-do-import"),
]
