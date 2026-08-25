from pathlib import Path

SQL = (Path(__file__).parents[2] / "supabase" / "u4-data-graph.sql").read_text()


def test_rls_and_explicit_data_api_grants() -> None:
    for table in ("namespace_records", "lineage_edges"):
        assert f"alter table public.{table} enable row level security" in SQL
    assert "revoke all on table" in SQL
    assert "grant select, insert, update, delete" in SQL


def test_foreign_keys_projection_and_retention_are_indexed() -> None:
    for index in (
        "namespace_records_expiration_idx",
        "lineage_edges_source_idx",
        "lineage_edges_target_idx",
        "lineage_edges_projection_idx",
    ):
        assert index in SQL
    assert "where expires_at is not null" in SQL


def test_lineage_policy_requires_same_isolation() -> None:
    for clause in (
        "source.organization_id = organization_id",
        "target.organization_id = organization_id",
        "source.namespace = namespace",
        "target.namespace = namespace",
    ):
        assert clause in SQL
