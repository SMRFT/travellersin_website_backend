import json
import ast
from collections import OrderedDict
import djongo.models as dj_models


class SafeJSONField(dj_models.JSONField):
    def _to_native_json(self, value):
        if value is None:
            if callable(self.default):
                return self.default()
            if isinstance(self.default, (dict, list)):
                return self.default
            return {}
        if isinstance(value, OrderedDict):
            return dict(value)
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, str):
            val_str = value.strip()
            if not val_str:
                return [] if isinstance(self.default, list) or (callable(self.default) and isinstance(self.default(), list)) else {}
            if val_str.startswith("OrderedDict(") and val_str.endswith(")"):
                val_str = val_str[12:-1]
            try:
                parsed = json.loads(val_str)
                if isinstance(parsed, (dict, list)):
                    return parsed
            except Exception:
                pass
            try:
                parsed = ast.literal_eval(val_str)
                if isinstance(parsed, (dict, list)):
                    return parsed
            except Exception:
                pass
        return [] if isinstance(self.default, list) or (callable(self.default) and isinstance(self.default(), list)) else {}

    def get_prep_value(self, value):
        return self._to_native_json(value)

    def to_python(self, value):
        return self._to_native_json(value)
