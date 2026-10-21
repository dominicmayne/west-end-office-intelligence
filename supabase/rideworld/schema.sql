-- RideWorld pilot backend. Paste into Supabase > SQL Editor and run once.
-- Parents (anon) can read ride names, log a scan and send a fault. Nothing else.
-- Signed-in staff (users you invite in Authentication > Users) can read everything and mark faults fixed.

create table if not exists rides (
  id text primary key check (id ~ '^[A-Z0-9-]{2,16}$'),  -- printed on the sticker, e.g. RO-0412
  name text not null,
  centre text not null,
  spot text not null default '',                          -- where it sits, e.g. Level 1, outside Toy Town
  emoji text not null default '🎡',
  colour text not null default '#ff3b30',
  created_at timestamptz not null default now()
);

create table if not exists faults (
  id bigint generated always as identity primary key,
  ride_id text not null references rides (id),
  issue text not null check (issue in ('Won’t start', 'Payment not working', 'No music or lights', 'Something’s broken', 'Other')),
  created_at timestamptz not null default now(),
  fixed_at timestamptz,
  fixed_by uuid
);
create index if not exists faults_ride_time on faults (ride_id, created_at desc);

create table if not exists scans (
  id bigint generated always as identity primary key,
  ride_id text not null references rides (id),
  created_at timestamptz not null default now()
);
create index if not exists scans_ride_time on scans (ride_id, created_at desc);

-- Spam guard: one ride takes at most 3 fault reports and 120 scans in 10 minutes
create or replace function rideworld_limit() returns trigger language plpgsql security definer set search_path = public as $$
declare n int;
begin
  if tg_table_name = 'faults' then
    select count(*) into n from faults where ride_id = new.ride_id and created_at > now() - interval '10 minutes';
    if n >= 3 then raise exception 'Too many reports for this ride, try again later' using errcode = 'P0001'; end if;
    new.created_at := now(); new.fixed_at := null; new.fixed_by := null;
  else
    select count(*) into n from scans where ride_id = new.ride_id and created_at > now() - interval '10 minutes';
    if n >= 120 then raise exception 'Too many scans' using errcode = 'P0001'; end if;
    new.created_at := now();
  end if;
  return new;
end $$;
drop trigger if exists faults_limit on faults;
create trigger faults_limit before insert on faults for each row execute function rideworld_limit();
drop trigger if exists scans_limit on scans;
create trigger scans_limit before insert on scans for each row execute function rideworld_limit();

-- Marking fixed records who did it
create or replace function rideworld_fixed() returns trigger language plpgsql as $$
begin
  if new.fixed_at is not null and old.fixed_at is null then new.fixed_by := auth.uid(); end if;
  new.ride_id := old.ride_id; new.issue := old.issue; new.created_at := old.created_at;
  return new;
end $$;
drop trigger if exists faults_fixed on faults;
create trigger faults_fixed before update on faults for each row execute function rideworld_fixed();

alter table rides enable row level security;
alter table faults enable row level security;
alter table scans enable row level security;

drop policy if exists "anyone reads rides" on rides;
create policy "anyone reads rides" on rides for select to anon, authenticated using (true);
drop policy if exists "anyone reports" on faults;
create policy "anyone reports" on faults for insert to anon, authenticated with check (fixed_at is null);
drop policy if exists "staff read faults" on faults;
create policy "staff read faults" on faults for select to authenticated using (true);
drop policy if exists "staff fix faults" on faults;
create policy "staff fix faults" on faults for update to authenticated using (true) with check (true);
drop policy if exists "anyone scans" on scans;
create policy "anyone scans" on scans for insert to anon, authenticated with check (true);
drop policy if exists "staff read scans" on scans;
create policy "staff read scans" on scans for select to authenticated using (true);

revoke all on rides, faults, scans from anon, authenticated;
grant select on rides to anon, authenticated;
grant insert (ride_id, issue) on faults to anon, authenticated;
grant insert (ride_id) on scans to anon, authenticated;
grant select on faults, scans to authenticated;
grant update (fixed_at) on faults to authenticated;

-- Weekly numbers per ride, for the log and the Monday email
create or replace view weekly_numbers with (security_invoker = true) as
select r.id, r.name, r.centre,
  (select count(*) from scans s where s.ride_id = r.id and s.created_at > now() - interval '7 days') as scans,
  (select count(*) from faults f where f.ride_id = r.id and f.created_at > now() - interval '7 days') as faults,
  (select avg(f.fixed_at - f.created_at) from faults f where f.ride_id = r.id and f.fixed_at > now() - interval '7 days') as avg_fix
from rides r;
grant select on weekly_numbers to authenticated;

-- Example rides: replace with Craig's real list (ride number, name, centre, where it sits)
-- insert into rides (id, name, centre, spot, emoji, colour) values
--   ('RO-0412', 'Red Racer', 'Red Dragon Centre', 'Ground floor, by the cinema', '🏎️', '#ff3b30');
