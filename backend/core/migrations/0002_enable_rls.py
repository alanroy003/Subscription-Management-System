"""Defense in depth on Supabase: enable RLS (no policies) on every app table in the public schema.

Supabase exposes the public schema through its Data API with the publishable key. With RLS enabled and no
policies, that API sees nothing. Django connects as the table owner, which RLS does not restrict.
"""
from django.db import migrations

SQL_TABLES = "select tablename from pg_tables where schemaname = 'public'"


def toggle(enable):
    def run(apps, schema_editor):
        if schema_editor.connection.vendor != "postgresql":
            return
        with schema_editor.connection.cursor() as cur:
            cur.execute(SQL_TABLES)
            for (table,) in cur.fetchall():
                verb = "enable" if enable else "disable"
                cur.execute(f'alter table public."{table}" {verb} row level security')
    return run


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial"), ("accounts", "0001_initial"), ("authtoken", "0004_alter_tokenproxy_options"),
                    ("sessions", "0001_initial"), ("admin", "0003_logentry_add_action_flag_choices")]
    operations = [migrations.RunPython(toggle(True), toggle(False))]
