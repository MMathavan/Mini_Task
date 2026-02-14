from django.db import migrations


def seed_default_denominations(apps, schema_editor):
    Denomination = apps.get_model("Billing_App", "Denomination")
    default_values = [500, 200, 100, 50, 20, 10, 5, 2, 1]
    for value in default_values:
        Denomination.objects.get_or_create(
            DENOMVALUE=value,
            defaults={"DISPSTATUS": 0},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("Billing_App", "0005_invoice_emailfailcount_invoice_emaillasterror"),
    ]

    operations = [
        migrations.RunPython(seed_default_denominations, migrations.RunPython.noop),
    ]
