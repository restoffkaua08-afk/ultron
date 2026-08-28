-- U4/U6 cloud schema candidate. Converter em migration oficial somente com a
-- CLI e aplicar em um projeto Supabase dedicado ao ULTRON.
create table public.namespace_records (
  id uuid primary key default gen_random_uuid(), organization_id uuid not null references public.organizations(id) on delete cascade,
  namespace text not null check (namespace ~ '^[a-z0-9][a-z0-9._-]{0,62}$'), record_key text not null check (record_key ~ '^[a-z0-9][a-z0-9._-]{0,62}$'),
  owner_consumer_id uuid not null, value jsonb not null,
  created_at timestamptz not null default now(), expires_at timestamptz,
  unique (organization_id, namespace, record_key),
  unique (organization_id, namespace, id),
  foreign key (organization_id, owner_consumer_id)
    references public.ai_consumers(organization_id, id) on delete cascade
);
create index namespace_records_owner_idx on public.namespace_records (owner_consumer_id);
create index namespace_records_lookup_idx on public.namespace_records (organization_id, namespace, record_key);
create index namespace_records_expiration_idx on public.namespace_records (organization_id, namespace, expires_at) where expires_at is not null;
create table public.lineage_edges (
  id uuid primary key default gen_random_uuid(), organization_id uuid not null references public.organizations(id) on delete cascade,
  namespace text not null check (namespace ~ '^[a-z0-9][a-z0-9._-]{0,62}$'),
  source_record_id uuid not null, target_record_id uuid not null,
  relation text not null check (relation ~ '^[a-z0-9][a-z0-9._-]{0,62}$'),
  created_at timestamptz not null default now(),
  check (source_record_id <> target_record_id),
  unique (organization_id, namespace, source_record_id, target_record_id, relation),
  foreign key (organization_id, namespace, source_record_id)
    references public.namespace_records(organization_id, namespace, id) on delete cascade,
  foreign key (organization_id, namespace, target_record_id)
    references public.namespace_records(organization_id, namespace, id) on delete cascade
);
create index lineage_edges_source_idx on public.lineage_edges (source_record_id);
create index lineage_edges_target_idx on public.lineage_edges (target_record_id);
create index lineage_edges_projection_idx on public.lineage_edges (organization_id, namespace, relation);
alter table public.namespace_records enable row level security;
alter table public.lineage_edges enable row level security;
revoke all on table public.namespace_records, public.lineage_edges from anon, authenticated;
grant select, insert, update, delete on table public.namespace_records, public.lineage_edges to authenticated;
create policy namespace_records_select on public.namespace_records for select to authenticated using ((select private.is_org_member(organization_id)));
create policy namespace_records_insert on public.namespace_records for insert to authenticated with check ((select private.has_org_role(organization_id, array['owner','admin','developer']::public.organization_role[])));
create policy namespace_records_update on public.namespace_records for update to authenticated using ((select private.has_org_role(organization_id, array['owner','admin','developer']::public.organization_role[]))) with check ((select private.has_org_role(organization_id, array['owner','admin','developer']::public.organization_role[])));
create policy namespace_records_delete on public.namespace_records for delete to authenticated using ((select private.has_org_role(organization_id, array['owner','admin']::public.organization_role[])));
create policy lineage_edges_select on public.lineage_edges for select to authenticated using ((select private.is_org_member(organization_id)));
create policy lineage_edges_insert on public.lineage_edges for insert to authenticated with check (
  (select private.has_org_role(organization_id, array['owner','admin','developer']::public.organization_role[])) and exists (
    select 1 from public.namespace_records source, public.namespace_records target where source.id = source_record_id and target.id = target_record_id
      and source.organization_id = organization_id and target.organization_id = organization_id and source.namespace = namespace and target.namespace = namespace));
create policy lineage_edges_delete on public.lineage_edges for delete to authenticated using ((select private.has_org_role(organization_id, array['owner','admin']::public.organization_role[])));
