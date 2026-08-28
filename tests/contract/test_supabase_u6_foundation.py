"""Contratos estáticos do primeiro incremento do gate U6."""

from pathlib import Path

ROOT = Path(__file__).parents[2]
SCHEMA = (ROOT / "supabase" / "schema.sql").read_text()
GRAPH = (ROOT / "supabase" / "u4-data-graph.sql").read_text()


def test_new_objects_do_not_inherit_data_api_grants() -> None:
    for statement in (
        "alter default privileges for role postgres in schema public",
        "revoke select, insert, update, delete on tables",
        "revoke usage, select on sequences",
        "revoke execute on functions",
    ):
        assert statement in SCHEMA


def test_authenticated_grants_are_table_specific() -> None:
    assert "grant select, insert, update, delete on all tables" not in SCHEMA
    assert "grant select, update on table public.profiles" in SCHEMA
    assert "grant select on table public.audit_events" in SCHEMA
    assert "grant select, insert, update, delete on table public.ai_consumers" in SCHEMA


def test_audit_actor_is_bound_to_same_organization() -> None:
    assert "foreign key (organization_id, actor_consumer_id)" in SCHEMA
    assert "references public.ai_consumers(organization_id, id)" in SCHEMA


def test_namespace_owner_is_bound_to_same_organization() -> None:
    assert "foreign key (organization_id, owner_consumer_id)" in GRAPH
    assert "references public.ai_consumers(organization_id, id)" in GRAPH


def test_lineage_foreign_keys_enforce_organization_and_namespace() -> None:
    assert "unique (organization_id, namespace, id)" in GRAPH
    for record_column in ("source_record_id", "target_record_id"):
        assert f"foreign key (organization_id, namespace, {record_column})" in GRAPH
        assert "references public.namespace_records(organization_id, namespace, id)" in GRAPH


def test_every_exposed_table_has_rls_enabled() -> None:
    tables = (
        "profiles",
        "organizations",
        "organization_members",
        "ai_consumers",
        "capabilities",
        "capability_versions",
        "capability_dependencies",
        "capability_grants",
        "installations",
        "audit_events",
    )
    for table in tables:
        assert f"alter table public.{table} enable row level security" in SCHEMA

    for table in ("namespace_records", "lineage_edges"):
        assert f"alter table public.{table} enable row level security" in GRAPH
