from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),

    # Invoice URLs
    path("invoice/", views.invoice_index, name="invoice_index"),
    path("invoice/add/", views.invoice_create, name="invoice_add"),
    path("invoice/<int:pk>/", views.invoice_detail, name="invoice_detail"),
    path("invoice/<int:pk>/delete/", views.invoice_delete, name="invoice_delete"),

    # Product Master URLs
    path("products/", views.product_index, name="product_index"),
    path("products/add/", views.product_add, name="product_add"),
    path("products/<int:pk>/edit/", views.product_edit, name="product_edit"),
    path("products/<int:pk>/delete/", views.product_delete, name="product_delete"),

    # Denomination Master URLs
    path("denominations/", views.denomination_index, name="denomination_index"),
    path("denominations/add/", views.denomination_add, name="denomination_add"),
    path("denominations/<int:pk>/edit/", views.denomination_edit, name="denomination_edit"),
    path("denominations/<int:pk>/delete/", views.denomination_delete, name="denomination_delete"),

    # Customer Master URLs
    path("customers/", views.customer_index, name="customer_index"),
    path("customers/add/", views.customer_add, name="customer_add"),
    path("customers/<int:pk>/edit/", views.customer_edit, name="customer_edit"),
    path("customers/<int:pk>/delete/", views.customer_delete, name="customer_delete"),
]
