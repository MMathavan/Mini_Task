import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.db.models import F

from .models import Invoice

logger = logging.getLogger(__name__)


def _build_invoice_email_body(invoice):
    lines = [
        f"Invoice No: {invoice.INVOICEID}",
        f"Customer Name: {invoice.CUSTNAME}",
        f"Customer Email: {invoice.CUSTEMAIL}",
        "",
        "Purchased Items:",
    ]

    for item in invoice.items.select_related("PRODUCT").all():
        lines.append(
            f"- {item.PRODUCT.PRODNAME} ({item.PRODUCT.PRODCODE}) | Qty: {item.QTY} | "
            f"Unit: {item.UNITPRICE} | Tax: {item.LINETAX} | Total: {item.LINETOTAL}"
        )

    lines.extend(
        [
            "",
            f"Gross Amount: {invoice.GROSSAMT}",
            f"Tax Amount: {invoice.TAXAMT}",
            f"Net Amount: {invoice.NETAMT}",
            f"Rounded Payable: {invoice.ROUNDEDPAYABLE}",
            f"Paid Amount: {invoice.PAIDAMT}",
            f"Balance Amount: {invoice.BALANCEAMT}",
            "",
            "Thank you for your purchase.",
        ]
    )
    return "\n".join(lines)


@shared_task(bind=True, max_retries=5, retry_backoff=True, retry_jitter=True)
def send_invoice_email_task(self, invoice_id):
    try:
        invoice = Invoice.objects.get(pk=invoice_id)
        subject = f"Invoice #{invoice.INVOICEID}"
        body = _build_invoice_email_body(invoice)

        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invoice.CUSTEMAIL],
            fail_silently=False,
        )

        invoice.EMAILSENT = True
        invoice.EMAILLASTERROR = ""
        invoice.save(update_fields=["EMAILSENT", "EMAILLASTERROR"])
        return {"status": "sent", "invoice_id": invoice_id}
    except Exception as exc:
        Invoice.objects.filter(pk=invoice_id).update(
            EMAILFAILCOUNT=F("EMAILFAILCOUNT") + 1,
            EMAILLASTERROR=str(exc)[:1000],
            EMAILSENT=False,
        )
        logger.exception("Invoice email failed for invoice_id=%s", invoice_id)
        raise self.retry(exc=exc)
