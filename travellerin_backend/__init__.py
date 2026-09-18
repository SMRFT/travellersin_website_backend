from decimal import Decimal
from django.db.models.fields import DecimalField
from bson.decimal128 import Decimal128

orig_to_python = DecimalField.to_python

def patched_to_python(self, value):
    if isinstance(value, Decimal128):
        return value.to_decimal()
    return orig_to_python(self, value)

DecimalField.to_python = patched_to_python
