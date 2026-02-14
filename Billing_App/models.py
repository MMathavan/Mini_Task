from django.db import models
from django.utils import timezone
from decimal import Decimal


class Product(models.Model):

    # Primary Key
    PRODID = models.AutoField(primary_key=True)
    # Product Name
    PRODNAME = models.CharField(max_length=200)
    # Product Business Code
    PRODCODE = models.CharField(max_length=50, unique=True)
    # Price of One Unit
    PRODPRI = models.DecimalField(max_digits=10, decimal_places=2)
    # Available Stock Quantity
    PROAVASTOCK = models.PositiveIntegerField()
    # Tax Percentage
    PRODTAXPRE = models.DecimalField(max_digits=5, decimal_places=2)
    # Display Status
    # 0 = Enabled
    # 1 = Disabled
    DISPSTATUS = models.IntegerField(
        choices=(
            (0, "Enabled"),
            (1, "Disabled"),
        )
    )
    # Created Date
    PRCSDATE = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = "PRODUCT_MASTER"
        ordering = ["-PRCSDATE"]
    def get_price_with_tax(self):
        tax_amount = (self.PRODPRI * self.PRODTAXPRE) / Decimal("100")
        return self.PRODPRI + tax_amount
    def __str__(self):
        return f"{self.PRODNAME} ({self.PRODCODE})"


class Denomination(models.Model):

    # Primary Key
    DENOMID = models.AutoField(primary_key=True)
    # Denomination Value (Example: 500, 200, 100)
    DENOMVALUE = models.PositiveIntegerField(unique=True)
    # Display Status
    # 0 = Enabled
    # 1 = Disabled
    DISPSTATUS = models.IntegerField(
        choices=(
            (0, "Enabled"),
            (1, "Disabled"),
        )
    )
    # Created Date
    PRCSDATE = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = "DENOMINATION_MASTER"
        ordering = ["-DENOMVALUE"]
    def __str__(self):
        return f"{self.DENOMVALUE}"
    

class Customer(models.Model):

    # Primary Key
    CUSTID = models.AutoField(primary_key=True)
    # Customer Name
    CUSTNAME = models.CharField(max_length=200)
    # Customer Email (Unique)
    CUSTEMAIL = models.EmailField(unique=True)
    # Display Status
    # 0 = Enabled
    # 1 = Disabled
    DISPSTATUS = models.IntegerField(
        choices=(
            (0, "Enabled"),
            (1, "Disabled"),
        )
    )
    # Created Date
    PRCSDATE = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = "CUSTOMER_MASTER"
        ordering = ["-PRCSDATE"]
    def __str__(self):
        return f"{self.CUSTNAME} ({self.CUSTEMAIL})"
    

class Invoice(models.Model):
    # Primary Key
    INVOICEID = models.AutoField(primary_key=True)
    # Customer Name
    CUSTNAME = models.CharField(max_length=200, default="")
    # Customer Email (Indexed for faster lookups)
    CUSTEMAIL = models.EmailField(db_index=True)
    
    GROSSAMT = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    TAXAMT = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    NETAMT = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    ROUNDEDPAYABLE = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    PAIDAMT = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    BALANCEAMT = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    # Example: {"500": 2, "100": 1}
    RECEIVED_DENOMS = models.JSONField(default=dict, blank=True)
    CHANGE_DENOMS = models.JSONField(default=dict, blank=True)

    EMAILSENT = models.BooleanField(default=False)
    EMAILFAILCOUNT = models.PositiveIntegerField(default=0)
    EMAILLASTERROR = models.TextField(blank=True, default="")
    PRCSDATE = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "TRANSACTION_MASTER"
        ordering = ["-PRCSDATE"]

    def __str__(self):
        return f"Invoice {self.INVOICEID} - {self.CUSTEMAIL}"
    



class InvoiceItem(models.Model):
    INVOICEITEMID = models.AutoField(primary_key=True)
    INVOICE = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="items")
    PRODUCT = models.ForeignKey("Product", on_delete=models.PROTECT)

    UNITPRICE = models.DecimalField(max_digits=10, decimal_places=2)
    TAXPERCENT = models.DecimalField(max_digits=5, decimal_places=2)
    QTY = models.PositiveIntegerField()

    LINESUBTOTAL = models.DecimalField(max_digits=12, decimal_places=2)
    LINETAX = models.DecimalField(max_digits=12, decimal_places=2)
    LINETOTAL = models.DecimalField(max_digits=12, decimal_places=2)

    PRCSDATE = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "TRANSACTION_DETAILS"
        ordering = ["INVOICEITEMID"]

    def __str__(self):
        return f"InvoiceItem {self.INVOICEITEMID} - Invoice {self.INVOICE_ID}"




