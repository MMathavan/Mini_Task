from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Customer, Denomination, Invoice, Product
from .views import _queue_invoice_email


class InvoiceFlowTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            PRODNAME="Milk",
            PRODCODE="P001",
            PRODPRI=Decimal("20.00"),
            PRODTAXPRE=Decimal("5.00"),
            PROAVASTOCK=10,
            DISPSTATUS=0,
        )
        self.denom_100 = Denomination.objects.create(DENOMVALUE=1000, DISPSTATUS=0)
        self.denom_10 = Denomination.objects.create(DENOMVALUE=30, DISPSTATUS=0)

    @patch("Billing_App.views._queue_invoice_email")
    def test_invoice_create_success_and_customer_auto_create(self, mock_queue):
        payload = {
            "customer_name": "New Customer",
            "customer_email": "newcustomer@example.com",
            "product_id[]": [str(self.product.PRODID)],
            "quantity[]": ["2"],
            f"denom_{self.denom_100.DENOMID}": "1",
            f"denom_{self.denom_10.DENOMID}": "0",
        }

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("invoice_add"), data=payload)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Invoice.objects.count(), 1)

        invoice = Invoice.objects.first()
        self.assertEqual(invoice.CUSTNAME, "New Customer")
        self.assertEqual(invoice.CUSTEMAIL, "newcustomer@example.com")

        customer = Customer.objects.get(CUSTEMAIL="newcustomer@example.com")
        self.assertEqual(customer.CUSTNAME, "New Customer")

        self.product.refresh_from_db()
        self.assertEqual(self.product.PROAVASTOCK, 8)

        mock_queue.assert_called_once_with(invoice.INVOICEID)

    @patch("Billing_App.views._queue_invoice_email")
    def test_invoice_create_fails_on_insufficient_stock(self, mock_queue):
        payload = {
            "customer_name": "Stock User",
            "customer_email": "stock@example.com",
            "product_id[]": [str(self.product.PRODID)],
            "quantity[]": ["999"],
            f"denom_{self.denom_100.DENOMID}": "1",
            f"denom_{self.denom_10.DENOMID}": "0",
        }
        response = self.client.post(reverse("invoice_add"), data=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Invoice.objects.count(), 0)
        mock_queue.assert_not_called()

    def test_invoice_index_filters_name_email_date(self):
        now = timezone.now()
        i1 = Invoice.objects.create(
            CUSTNAME="Alice",
            CUSTEMAIL="alice@example.com",
            NETAMT=Decimal("50.00"),
            PAIDAMT=Decimal("100.00"),
            BALANCEAMT=Decimal("50.00"),
        )
        i2 = Invoice.objects.create(
            CUSTNAME="Bob",
            CUSTEMAIL="bob@example.com",
            NETAMT=Decimal("60.00"),
            PAIDAMT=Decimal("100.00"),
            BALANCEAMT=Decimal("40.00"),
        )
        Invoice.objects.filter(pk=i1.pk).update(PRCSDATE=now - timedelta(days=5))
        Invoice.objects.filter(pk=i2.pk).update(PRCSDATE=now)

        response = self.client.get(
            reverse("invoice_index"),
            data={
                "customer_name": "Bob",
                "customer_email": "bob@",
                "from_date": (now - timedelta(days=1)).date().isoformat(),
                "to_date": now.date().isoformat(),
            },
        )
        self.assertEqual(response.status_code, 200)
        invoices = list(response.context["invoices"].object_list)
        self.assertEqual(len(invoices), 1)
        self.assertEqual(invoices[0].CUSTNAME, "Bob")


class EmailQueueFallbackTests(TestCase):
    def test_queue_failure_updates_invoice_tracking_fields(self):
        invoice = Invoice.objects.create(
            CUSTNAME="Queue Test",
            CUSTEMAIL="queue@example.com",
            NETAMT=Decimal("10.00"),
            PAIDAMT=Decimal("20.00"),
            BALANCEAMT=Decimal("10.00"),
        )

        with patch("Billing_App.views.send_invoice_email_task.delay", side_effect=Exception("broker down")):
            _queue_invoice_email(invoice.INVOICEID)

        invoice.refresh_from_db()
        self.assertEqual(invoice.EMAILSENT, False)
        self.assertEqual(invoice.EMAILFAILCOUNT, 1)
        self.assertIn("Queue error:", invoice.EMAILLASTERROR)
