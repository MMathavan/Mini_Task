from django import forms

from .models import Customer, Denomination, Product


class BootstrapModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.Select):
                widget.attrs["class"] = "form-select"
            else:
                widget.attrs["class"] = "form-control"

            if field_name == "DISPSTATUS":
                field.choices = [choice for choice in field.choices if choice[0] != ""]


class ProductForm(BootstrapModelForm):
    class Meta:
        model = Product
        fields = ["PRODNAME", "PRODCODE", "PRODPRI", "PRODTAXPRE", "PROAVASTOCK", "DISPSTATUS"]
        labels = {
            "PRODNAME": "Product Name",
            "PRODCODE": "Product Code",
            "PRODPRI": "Unit Price",
            "PRODTAXPRE": "Tax Percentage",
            "PROAVASTOCK": "Available Stock",
            "DISPSTATUS": "Status",
        }


class DenominationForm(BootstrapModelForm):
    class Meta:
        model = Denomination
        fields = ["DENOMVALUE", "DISPSTATUS"]
        labels = {
            "DENOMVALUE": "Denomination Value",
            "DISPSTATUS": "Status",
        }


class CustomerForm(BootstrapModelForm):
    class Meta:
        model = Customer
        fields = ["CUSTNAME", "CUSTEMAIL", "DISPSTATUS"]
        labels = {
            "CUSTNAME": "Customer Name",
            "CUSTEMAIL": "Customer Email",
            "DISPSTATUS": "Status",
        }
