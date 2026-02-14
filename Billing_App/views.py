from decimal import Decimal, ROUND_DOWN
import logging

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F, Q
from django.shortcuts import get_object_or_404, redirect, render
from .forms import CustomerForm, DenominationForm, ProductForm
from .models import Customer, Denomination, Invoice, InvoiceItem, Product
from .tasks import send_invoice_email_task

logger = logging.getLogger(__name__)


def _queue_invoice_email(invoice_id):
    try:
        send_invoice_email_task.delay(invoice_id)
    except Exception as exc:
        logger.exception("Failed to queue invoice email task for invoice_id=%s", invoice_id)
        Invoice.objects.filter(pk=invoice_id).update(
            EMAILFAILCOUNT=F("EMAILFAILCOUNT") + 1,
            EMAILLASTERROR=f"Queue error: {str(exc)[:1000]}",
            EMAILSENT=False,
        )


def home(request):
    return redirect("invoice_index")


def invoice_index(request):
    customer_name = request.GET.get("customer_name", "").strip()
    customer_email = request.GET.get("customer_email", "").strip()
    from_date = request.GET.get("from_date", "").strip()
    to_date = request.GET.get("to_date", "").strip()
    per_page = _get_per_page(request)
    invoice_qs = Invoice.objects.all()

    if customer_name:
        invoice_qs = invoice_qs.filter(CUSTNAME__icontains=customer_name)
    if customer_email:
        invoice_qs = invoice_qs.filter(CUSTEMAIL__icontains=customer_email)
    if from_date:
        invoice_qs = invoice_qs.filter(PRCSDATE__date__gte=from_date)
    if to_date:
        invoice_qs = invoice_qs.filter(PRCSDATE__date__lte=to_date)

    paginator = Paginator(invoice_qs, per_page)
    page_obj = paginator.get_page(request.GET.get("page"))
    context = {
        "invoices": page_obj,
        "customer_name": customer_name,
        "customer_email": customer_email,
        "from_date": from_date,
        "to_date": to_date,
        "per_page": per_page,
    }
    return render(request, "Invoice/Invoice_Index.html", context)


def invoice_create(request):
    customers = Customer.objects.filter(DISPSTATUS=0).order_by("CUSTNAME")
    products = Product.objects.filter(DISPSTATUS=0).order_by("PRODNAME")
    denominations = Denomination.objects.filter(DISPSTATUS=0).order_by("-DENOMVALUE")

    if request.method == "GET":
        context = {
            "customers": customers,
            "products": products,
            "denominations": denominations,
        }
        return render(request, "Invoice/Invoice_Add.html", context)

    customer_name = request.POST.get("customer_name", "").strip()
    customer_email = request.POST.get("customer_email", "").strip().lower()

    if not customer_name:
        messages.error(request, "Customer name is required.")
        return render(
            request,
            "Invoice/Invoice_Add.html",
            {"customers": customers, "products": products, "denominations": denominations},
        )

    if not customer_email:
        messages.error(request, "Customer email is required.")
        return render(
            request,
            "Invoice/Invoice_Add.html",
            {"customers": customers, "products": products, "denominations": denominations},
        )

    product_ids = request.POST.getlist("product_id[]")
    quantities = request.POST.getlist("quantity[]")
    line_inputs = []
    for product_id, quantity in zip(product_ids, quantities):
        product_id = product_id.strip()
        quantity = quantity.strip()
        if not product_id and not quantity:
            continue
        line_inputs.append((product_id, quantity))

    if not line_inputs:
        messages.error(request, "Add at least one product line.")
        return render(
            request,
            "Invoice/Invoice_Add.html",
            {"customers": customers, "products": products, "denominations": denominations},
        )

    product_qty_map = {}
    for product_id, quantity in line_inputs:
        if not product_id or not quantity:
            messages.error(request, "Each bill row needs product and quantity.")
            return render(
                request,
                "Invoice/Invoice_Add.html",
                {
                    "customers": customers,
                    "products": products,
                    "denominations": denominations,
                },
            )
        try:
            pid = int(product_id)
            qty = int(quantity)
        except ValueError:
            messages.error(request, "Invalid product or quantity value.")
            return render(
                request,
                "Invoice/Invoice_Add.html",
                {
                    "customers": customers,
                    "products": products,
                    "denominations": denominations,
                },
            )
        if qty <= 0:
            messages.error(request, "Quantity must be greater than zero.")
            return render(
                request,
                "Invoice/Invoice_Add.html",
                {
                    "customers": customers,
                    "products": products,
                    "denominations": denominations,
                },
            )
        product_qty_map[pid] = product_qty_map.get(pid, 0) + qty

    product_map = {
        item.PRODID: item for item in Product.objects.filter(PRODID__in=product_qty_map.keys())
    }
    if len(product_map) != len(product_qty_map):
        messages.error(request, "One or more selected products do not exist.")
        return render(
            request,
            "Invoice/Invoice_Add.html",
            {"customers": customers, "products": products, "denominations": denominations},
        )

    for pid, qty in product_qty_map.items():
        product = product_map[pid]
        if product.DISPSTATUS != 0:
            messages.error(request, f"{product.PRODNAME} is disabled.")
            return render(
                request,
                "Invoice/Invoice_Add.html",
                {
                    "customers": customers,
                    "products": products,
                    "denominations": denominations,
                },
            )
        if qty > product.PROAVASTOCK:
            messages.error(
                request,
                f"Insufficient stock for {product.PRODNAME}. Available stock is {product.PROAVASTOCK}.",
            )
            return render(
                request,
                "Invoice/Invoice_Add.html",
                {
                    "customers": customers,
                    "products": products,
                    "denominations": denominations,
                },
            )

    received_denoms = {}
    paid_amount = Decimal("0.00")
    for denom in denominations:
        field_name = f"denom_{denom.DENOMID}"
        raw_count = request.POST.get(field_name, "0").strip() or "0"
        try:
            count = int(raw_count)
        except ValueError:
            messages.error(request, f"Invalid denomination count for {denom.DENOMVALUE}.")
            return render(
                request,
                "Invoice/Invoice_Add.html",
                {
                    "customers": customers,
                    "products": products,
                    "denominations": denominations,
                },
            )
        if count < 0:
            messages.error(request, "Denomination count cannot be negative.")
            return render(
                request,
                "Invoice/Invoice_Add.html",
                {
                    "customers": customers,
                    "products": products,
                    "denominations": denominations,
                },
            )
        received_denoms[str(denom.DENOMVALUE)] = count
        paid_amount += Decimal(denom.DENOMVALUE) * Decimal(count)

    paid_amount = paid_amount.quantize(Decimal("0.00"))

    gross_amount = Decimal("0.00")
    tax_amount = Decimal("0.00")
    item_payload = []

    for pid, qty in product_qty_map.items():
        product = product_map[pid]
        unit_price = product.PRODPRI.quantize(Decimal("0.00"))
        tax_percent = product.PRODTAXPRE.quantize(Decimal("0.00"))
        line_subtotal = (unit_price * qty).quantize(Decimal("0.00"))
        line_tax = (line_subtotal * tax_percent / Decimal("100")).quantize(Decimal("0.00"))
        line_total = (line_subtotal + line_tax).quantize(Decimal("0.00"))

        gross_amount += line_subtotal
        tax_amount += line_tax
        item_payload.append(
            {
                "product": product,
                "qty": qty,
                "unit_price": unit_price,
                "tax_percent": tax_percent,
                "line_subtotal": line_subtotal,
                "line_tax": line_tax,
                "line_total": line_total,
            }
        )

    gross_amount = gross_amount.quantize(Decimal("0.00"))
    tax_amount = tax_amount.quantize(Decimal("0.00"))
    net_amount = (gross_amount + tax_amount).quantize(Decimal("0.00"))
    rounded_payable = net_amount.to_integral_value(rounding=ROUND_DOWN).quantize(
        Decimal("0.00")
    )
    balance_amount = (paid_amount - rounded_payable).quantize(Decimal("0.00"))

    if balance_amount < 0:
        messages.error(
            request,
            "Cash paid by customer is less than rounded payable amount.",
        )
        return render(
            request,
            "Invoice/Invoice_Add.html",
            {"customers": customers, "products": products, "denominations": denominations},
        )

    change_denoms = {}
    remaining = int(balance_amount)
    for denom in denominations:
        value = int(denom.DENOMVALUE)
        if value <= 0:
            continue
        count = remaining // value
        if count > 0:
            change_denoms[str(value)] = count
            remaining -= count * value

    if remaining > 0:
        change_denoms["remaining"] = remaining

    with transaction.atomic():
        customer, created = Customer.objects.get_or_create(
            CUSTEMAIL=customer_email,
            defaults={"CUSTNAME": customer_name, "DISPSTATUS": 0},
        )
        if not created and customer.CUSTNAME != customer_name:
            customer.CUSTNAME = customer_name
            customer.save(update_fields=["CUSTNAME"])

        invoice = Invoice.objects.create(
            CUSTNAME=customer_name,
            CUSTEMAIL=customer_email,
            GROSSAMT=gross_amount,
            TAXAMT=tax_amount,
            NETAMT=net_amount,
            ROUNDEDPAYABLE=rounded_payable,
            PAIDAMT=paid_amount,
            BALANCEAMT=balance_amount,
            RECEIVED_DENOMS=received_denoms,
            CHANGE_DENOMS=change_denoms,
            EMAILSENT=False,
        )

        items = []
        for row in item_payload:
            items.append(
                InvoiceItem(
                    INVOICE=invoice,
                    PRODUCT=row["product"],
                    UNITPRICE=row["unit_price"],
                    TAXPERCENT=row["tax_percent"],
                    QTY=row["qty"],
                    LINESUBTOTAL=row["line_subtotal"],
                    LINETAX=row["line_tax"],
                    LINETOTAL=row["line_total"],
                )
            )
        InvoiceItem.objects.bulk_create(items)

        for row in item_payload:
            product = row["product"]
            product.PROAVASTOCK -= row["qty"]
            product.save(update_fields=["PROAVASTOCK"])

        transaction.on_commit(lambda: _queue_invoice_email(invoice.INVOICEID))

    messages.success(
        request,
        "Invoice generated successfully. Email queue triggered in background.",
    )
    return redirect("invoice_detail", pk=invoice.INVOICEID)


def invoice_detail(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    items = invoice.items.select_related("PRODUCT").all()
    context = {"invoice": invoice, "items": items}
    return render(request, "Invoice/Invoice_Detail.html", context)


def invoice_delete(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if request.method == "POST":
        invoice.delete()
        messages.success(request, "Invoice deleted successfully.")
    return redirect("invoice_index")


def _get_per_page(request):
    try:
        per_page = int(request.GET.get("per_page", 10))
    except ValueError:
        per_page = 10
    return per_page if per_page in [10, 20, 50, 100] else 10


def product_index(request):
    search_query = request.GET.get("search", "").strip()
    per_page = _get_per_page(request)
    product_qs = Product.objects.all()

    if search_query:
        product_qs = product_qs.filter(
            Q(PRODNAME__icontains=search_query) | Q(PRODCODE__icontains=search_query)
        )

    paginator = Paginator(product_qs, per_page)
    page_obj = paginator.get_page(request.GET.get("page"))
    context = {"products": page_obj, "search_query": search_query, "per_page": per_page}
    return render(request, "ProductMaster/Product_Index.html", context)


def product_add(request):
    form = ProductForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Product created successfully.")
        return redirect("product_index")
    return render(request, "ProductMaster/Product_Add.html", {"form": form})


def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    form = ProductForm(request.POST or None, instance=product)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Product updated successfully.")
        return redirect("product_index")
    return render(request, "ProductMaster/Product_Edit.html", {"form": form, "object": product})


def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        product.delete()
        messages.success(request, "Product deleted successfully.")
        return redirect("product_index")
    return render(request, "ProductMaster/Product_Delete.html", {"object": product})


def denomination_index(request):
    search_query = request.GET.get("search", "").strip()
    per_page = _get_per_page(request)
    denomination_qs = Denomination.objects.all()

    if search_query:
        if search_query.isdigit():
            denomination_qs = denomination_qs.filter(DENOMVALUE=int(search_query))
        else:
            denomination_qs = denomination_qs.none()

    paginator = Paginator(denomination_qs, per_page)
    page_obj = paginator.get_page(request.GET.get("page"))
    context = {
        "denominations": page_obj,
        "search_query": search_query,
        "per_page": per_page,
    }
    return render(request, "DenominationMaster/Denomination_Index.html", context)


def denomination_add(request):
    form = DenominationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Denomination created successfully.")
        return redirect("denomination_index")
    return render(request, "DenominationMaster/Denomination_Add.html", {"form": form})


def denomination_edit(request, pk):
    denomination = get_object_or_404(Denomination, pk=pk)
    form = DenominationForm(request.POST or None, instance=denomination)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Denomination updated successfully.")
        return redirect("denomination_index")
    return render(
        request,
        "DenominationMaster/Denomination_Edit.html",
        {"form": form, "object": denomination},
    )


def denomination_delete(request, pk):
    denomination = get_object_or_404(Denomination, pk=pk)
    if request.method == "POST":
        denomination.delete()
        messages.success(request, "Denomination deleted successfully.")
        return redirect("denomination_index")
    return render(
        request, "DenominationMaster/Denomination_Delete.html", {"object": denomination}
    )


def customer_index(request):
    search_query = request.GET.get("search", "").strip()
    per_page = _get_per_page(request)
    customer_qs = Customer.objects.all()

    if search_query:
        customer_qs = customer_qs.filter(
            Q(CUSTNAME__icontains=search_query) | Q(CUSTEMAIL__icontains=search_query)
        )

    paginator = Paginator(customer_qs, per_page)
    page_obj = paginator.get_page(request.GET.get("page"))
    context = {"customers": page_obj, "search_query": search_query, "per_page": per_page}
    return render(request, "CustomerMaster/Customer_Index.html", context)


def customer_add(request):
    form = CustomerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Customer created successfully.")
        return redirect("customer_index")
    return render(request, "CustomerMaster/Customer_Add.html", {"form": form})


def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    form = CustomerForm(request.POST or None, instance=customer)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Customer updated successfully.")
        return redirect("customer_index")
    return render(request, "CustomerMaster/Customer_Edit.html", {"form": form, "object": customer})


def customer_delete(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == "POST":
        customer.delete()
        messages.success(request, "Customer deleted successfully.")
        return redirect("customer_index")
    return render(request, "CustomerMaster/Customer_Delete.html", {"object": customer})
