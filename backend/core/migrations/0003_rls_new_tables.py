from django.db import migrations

from importlib import import_module

_rls = import_module("core.migrations.0002_enable_rls")


class Migration(migrations.Migration):
    """Re-applies RLS (no policies) so tables added since 0002 are also hidden from the Supabase Data API."""

    dependencies = [("core", "0002_enable_rls"), ("accounts", "0002_api_keys")]
    operations = [migrations.RunPython(_rls.toggle(True), migrations.RunPython.noop)]
