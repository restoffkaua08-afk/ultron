-- ULTRON U6 cloud schema candidate.
-- Ainda não é migration oficial: a CLI não está disponível neste ambiente e
-- nenhum projeto Supabase dedicado ao ULTRON foi identificado para aplicação.

-- Novos objetos nunca devem herdar exposição automática à Data API.
alter default privileges for role postgres in schema public
  revoke select, insert, update, delete on tables from anon, authenticated, service_role;
alter default privileges for role postgres in schema public
  revoke usage, select on sequences from anon, authenticated, service_role;
alter default privileges for role postgres in schema public
  revoke execute on functions from public, anon, authenticated, service_role;

create schema if not exists private;
revoke all on schema private from public, anon, authenticated;

create type public.organization_role as enum ('owner', 'admin', 'developer', 'viewer');
create type public.consumer_kind as enum ('claude', 'codex', 'zane', 'custom');
create type public.capability_visibility as enum ('private', 'organization', 'public');
create type public.installation_status as enum ('installed', 'active', 'disabled', 'failed');

create table public.profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  github_login text,
  display_name text,
  avatar_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.organizations (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique check (slug ~ '^[a-z0-9][a-z0-9-]{1,62}$'),
  name text not null check (char_length(name) between 1 and 120),
  personal_owner_id uuid unique references auth.users(id) on delete cascade,
  created_at timestamptz not null default now()
);

create table public.organization_members (
  organization_id uuid not null references public.organizations(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role public.organization_role not null default 'viewer',
  created_at timestamptz not null default now(),
  primary key (organization_id, user_id)
);

create index organization_members_user_idx
  on public.organization_members (user_id, organization_id);

create table public.ai_consumers (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  name text not null check (char_length(name) between 1 and 120),
  kind public.consumer_kind not null,
  external_subject text,
  enabled boolean not null default true,
  last_seen_at timestamptz,
  created_at timestamptz not null default now(),
  unique (organization_id, name),
  unique (organization_id, id)
);

create index ai_consumers_organization_idx
  on public.ai_consumers (organization_id, enabled);

create table public.capabilities (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid references public.organizations(id) on delete cascade,
  manifest_id text not null check (manifest_id ~ '^[a-z0-9][a-z0-9._-]*/[a-z0-9][a-z0-9._-]*$'),
  kind text not null check (kind in ('agent', 'skill', 'workflow', 'pack')),
  visibility public.capability_visibility not null default 'private',
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  unique nulls not distinct (organization_id, manifest_id)
);

create index capabilities_discovery_idx
  on public.capabilities (visibility, kind, manifest_id);

create table public.capability_versions (
  id uuid primary key default gen_random_uuid(),
  capability_id uuid not null references public.capabilities(id) on delete cascade,
  version text not null,
  status text not null default 'published' check (status in ('published', 'deprecated', 'revoked')),
  manifest jsonb not null,
  manifest_sha256 text not null check (manifest_sha256 ~ '^[0-9a-f]{64}$'),
  artifact_sha256 text check (artifact_sha256 is null or artifact_sha256 ~ '^[0-9a-f]{64}$'),
  published_at timestamptz not null default now(),
  unique (capability_id, version)
);

create index capability_versions_lookup_idx
  on public.capability_versions (capability_id, status, published_at desc);

create table public.capability_dependencies (
  version_id uuid not null references public.capability_versions(id) on delete cascade,
  dependency_manifest_id text not null,
  version_range text not null,
  optional boolean not null default false,
  primary key (version_id, dependency_manifest_id)
);

create table public.capability_grants (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  consumer_id uuid not null,
  capability_id uuid not null references public.capabilities(id) on delete cascade,
  scopes text[] not null default '{}',
  granted_by uuid references auth.users(id) on delete set null,
  expires_at timestamptz,
  revoked_at timestamptz,
  created_at timestamptz not null default now(),
  unique (consumer_id, capability_id),
  foreign key (organization_id, consumer_id)
    references public.ai_consumers(organization_id, id) on delete cascade
);

create index capability_grants_active_idx
  on public.capability_grants (consumer_id, capability_id)
  where revoked_at is null;

create table public.installations (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  consumer_id uuid not null,
  capability_version_id uuid not null references public.capability_versions(id),
  status public.installation_status not null default 'installed',
  lockfile jsonb not null,
  installed_by uuid references auth.users(id) on delete set null,
  installed_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (consumer_id, capability_version_id),
  foreign key (organization_id, consumer_id)
    references public.ai_consumers(organization_id, id) on delete cascade
);

create index installations_scope_idx
  on public.installations (organization_id, consumer_id, status, updated_at desc);

create table public.audit_events (
  id bigint generated always as identity primary key,
  organization_id uuid not null references public.organizations(id) on delete cascade,
  actor_user_id uuid references auth.users(id) on delete set null,
  actor_consumer_id uuid,
  action text not null,
  target_type text,
  target_id text,
  payload jsonb not null default '{}',
  occurred_at timestamptz not null default now(),
  foreign key (organization_id, actor_consumer_id)
    references public.ai_consumers(organization_id, id) on delete set null
);

create index audit_events_timeline_idx
  on public.audit_events (organization_id, occurred_at desc);

create or replace function private.is_org_member(target_org uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.organization_members membership
    where membership.organization_id = target_org
      and membership.user_id = (select auth.uid())
  );
$$;

revoke all on function private.is_org_member(uuid) from public;
grant usage on schema private to authenticated;
grant execute on function private.is_org_member(uuid) to authenticated;

create or replace function private.has_org_role(
  target_org uuid,
  allowed_roles public.organization_role[]
)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.organization_members membership
    where membership.organization_id = target_org
      and membership.user_id = (select auth.uid())
      and membership.role = any(allowed_roles)
  );
$$;

revoke all on function private.has_org_role(uuid, public.organization_role[]) from public;
grant execute on function private.has_org_role(uuid, public.organization_role[]) to authenticated;

create or replace function private.bootstrap_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  new_organization_id uuid;
  base_name text;
begin
  base_name := coalesce(
    nullif(new.raw_user_meta_data ->> 'user_name', ''),
    nullif(new.raw_user_meta_data ->> 'name', ''),
    'ULTRON User'
  );

  insert into public.profiles (user_id, github_login, display_name, avatar_url)
  values (
    new.id,
    nullif(new.raw_user_meta_data ->> 'user_name', ''),
    base_name,
    nullif(new.raw_user_meta_data ->> 'avatar_url', '')
  );

  insert into public.organizations (slug, name, personal_owner_id)
  values ('user-' || replace(new.id::text, '-', ''), base_name, new.id)
  returning id into new_organization_id;

  insert into public.organization_members (organization_id, user_id, role)
  values (new_organization_id, new.id, 'owner');

  return new;
end;
$$;

revoke all on function private.bootstrap_user() from public, anon, authenticated;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function private.bootstrap_user();

alter table public.profiles enable row level security;
alter table public.organizations enable row level security;
alter table public.organization_members enable row level security;
alter table public.ai_consumers enable row level security;
alter table public.capabilities enable row level security;
alter table public.capability_versions enable row level security;
alter table public.capability_dependencies enable row level security;
alter table public.capability_grants enable row level security;
alter table public.installations enable row level security;
alter table public.audit_events enable row level security;

create policy profiles_self_select on public.profiles for select to authenticated
  using ((select auth.uid()) = user_id);
create policy profiles_self_update on public.profiles for update to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

create policy organizations_member_select on public.organizations for select to authenticated
  using ((select private.is_org_member(id)));
create policy members_member_select on public.organization_members for select to authenticated
  using ((select private.is_org_member(organization_id)));

create policy consumers_member_all on public.ai_consumers for all to authenticated
  using ((select private.has_org_role(organization_id, array['owner', 'admin', 'developer']::public.organization_role[])))
  with check ((select private.has_org_role(organization_id, array['owner', 'admin', 'developer']::public.organization_role[])));

create policy capabilities_discover on public.capabilities for select to authenticated
  using (visibility = 'public' or (organization_id is not null and (select private.is_org_member(organization_id))));
create policy capabilities_member_write on public.capabilities for all to authenticated
  using (organization_id is not null and (select private.has_org_role(organization_id, array['owner', 'admin', 'developer']::public.organization_role[])))
  with check (organization_id is not null and (select private.has_org_role(organization_id, array['owner', 'admin', 'developer']::public.organization_role[])));

create policy versions_visible_select on public.capability_versions for select to authenticated
  using (exists (
    select 1 from public.capabilities capability
    where capability.id = capability_id
      and (capability.visibility = 'public' or (capability.organization_id is not null and (select private.is_org_member(capability.organization_id))))
  ));

create policy dependencies_visible_select on public.capability_dependencies for select to authenticated
  using (exists (
    select 1 from public.capability_versions version
    join public.capabilities capability on capability.id = version.capability_id
    where version.id = version_id
      and (capability.visibility = 'public' or (capability.organization_id is not null and (select private.is_org_member(capability.organization_id))))
  ));

create policy grants_member_all on public.capability_grants for all to authenticated
  using ((select private.has_org_role(organization_id, array['owner', 'admin']::public.organization_role[])))
  with check ((select private.has_org_role(organization_id, array['owner', 'admin']::public.organization_role[])));
create policy installations_member_all on public.installations for all to authenticated
  using ((select private.has_org_role(organization_id, array['owner', 'admin', 'developer']::public.organization_role[])))
  with check ((select private.has_org_role(organization_id, array['owner', 'admin', 'developer']::public.organization_role[])));
create policy audit_member_select on public.audit_events for select to authenticated
  using ((select private.is_org_member(organization_id)));

-- Data API: acesso ao objeto e isolamento de linhas são decisões separadas.
-- Primeiro revoga tudo; depois concede somente as operações necessárias.
revoke all on all tables in schema public from anon, authenticated;
revoke all on all sequences in schema public from anon, authenticated;

grant select, update on table public.profiles to authenticated;
grant select on table public.organizations, public.organization_members to authenticated;
grant select, insert, update, delete on table public.ai_consumers to authenticated;
grant select, insert, update, delete on table public.capabilities to authenticated;
grant select on table public.capability_versions, public.capability_dependencies to authenticated;
grant select, insert, update, delete on table public.capability_grants to authenticated;
grant select, insert, update, delete on table public.installations to authenticated;
grant select on table public.audit_events to authenticated;
