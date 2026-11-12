# Mi Fitness — Home Assistant

Unofficial Home Assistant integration that pulls health & fitness data (steps,
heart rate, sleep, vitality, SpO₂, weight, stand hours …) from the Xiaomi **Mi
Fitness / MiHealth** cloud. Data is read at the account level — whatever your
Xiaomi devices (bands, scales, …) sync to Mi Fitness shows up, regardless of
which device produced it.

> ⚠️ **Disclaimer — educational / unofficial.**
> Not affiliated with, authorized, or endorsed by Xiaomi. It talks to a private
> cloud API by reusing your own account session, which may break at any time and
> may be against Xiaomi's Terms of Service. Use at your own risk, with your own
> account only.

## Provenance

This repository is a fork that collects the work available upstream. Sources:

- [batareya16/MiFitnessHass](https://github.com/batareya16/MiFitnessHass) — the
  original project (base: v1.0.8).
- [WG73/MiFitnessHass](https://github.com/WG73/MiFitnessHass) v1.1.2 — stress
  sensor ([PR #4](https://github.com/batareya16/MiFitnessHass/pull/4)),
  long-term statistics for heart rate, SpO₂ and steps
  ([PR #5](https://github.com/batareya16/MiFitnessHass/pull/5)), sleep duration
  for interrupted nights ([PR #6](https://github.com/batareya16/MiFitnessHass/pull/6)),
  state saved after merge ([PR #7](https://github.com/batareya16/MiFitnessHass/pull/7)).
- [Reasno/MiFitnessHass](https://github.com/Reasno/MiFitnessHass) — refresh
  token persistence, rotated `passToken` persistence, dynamic OTP channel
  (SMS / email), stable login `deviceId` with `trust=true`, complete sleep
  sessions, polling that survives network errors.
- [PR #1](https://github.com/batareya16/MiFitnessHass/pull/1) — `cn` region
  served from the bare `hlth.io.mi.com` host.
- Added here: time-window polling through `get_fitness_data_by_time` instead of
  the incremental watermark endpoint.

## Features

- Sensors: steps, distance, calories, heart rate (avg/max/min/resting), sleep
  (duration, stages, quality, chronotype), vitality, stand hours, SpO₂, stress,
  weight.
- Long-term statistics from every synced reading: hourly heart rate and SpO₂
  (mean/min/max) and steps — see [History statistics](#history-statistics).
- Silent token refresh using `passToken` — survives `serviceToken` expiry
  without re-doing 2FA.
- Custom Lovelace cards for activity and sleep (in [`www/`](www/)).

## Data source

Data is read by **time window**: the first poll covers 14 days, every later poll
re-reads the last 3 days, and the windows are merged idempotently (steps are
deduplicated by timestamp, heart rate/SpO₂ only move forward). The legacy
incremental endpoint is gone from the code.

Metrics your account does not produce simply return an empty page — for example
sleep without sleep tracking or weight without a scale; those sensors stay
unavailable.

## Installation

Add this repository as a custom **Integration** repository in HACS, or copy
`custom_components/mi_fitness/` into your Home Assistant
`config/custom_components/` directory, then restart Home Assistant and use
**Settings → Devices & Services → Add Integration → Mi Fitness**.

## Setup

Two authentication paths in the config flow:

### A. Username + password (recommended)
Enter your Xiaomi account email/phone and password. If 2FA is enabled, the code
is delivered through the channel Xiaomi selects for the account (SMS or email)
and entered in the next step. The integration stores a `passToken`, the rotated
tokens and the login `deviceId`, so it can refresh expired session tokens
silently and does not ask for 2FA again.

### B. Manual token entry
Advanced fallback for accounts where automated login fails. Supply credentials
obtained from your own Mi Fitness account session:

- `ssecurity`, `userId`, `cUserId` — from the `serviceLoginAuth2` response
- `passToken` — from the `serviceLoginAuth2` `Set-Cookie` header
- `serviceToken` — from the STS `Set-Cookie` header

Paste them into the form. `passToken` is optional but strongly recommended (it
enables silent refresh).

## Lovelace cards

The integration ships custom cards (in
[`custom_components/mi_fitness/www/`](custom_components/mi_fitness/www/)) and
**registers them automatically** — no manual resource setup needed.

```yaml
type: custom:mi-fitness-sleep-card

type: custom:mi-fitness-sleep-streak-card
goal_hours: 7
goal_minutes: 30
name: Sleep Goal

type: custom:mi-fitness-activity-card
step_goal: 6000

type: custom:mi-fitness-activity-streak-card
step_goal: 6000
name: Step Goal
```

The account is detected automatically from your entities — no `user_id` needed.
Only set it to disambiguate when you have **more than one** Mi Fitness account
configured:

```yaml
type: custom:mi-fitness-sleep-card
user_id: "1234567890"   # optional; the suffix in sensor.mi_fitness_<user_id>_…
```

> To find it manually: **Developer Tools → States**, filter `mi_fitness` — the
> number in the entity id (e.g. `sensor.mi_fitness_1234567890_steps_today`) is
> your `user_id`.

> After updating the integration, hard-refresh the browser (Ctrl+Shift+R) so
> the new card code loads.

## History statistics

The heart rate and SpO₂ sensors show the latest reading at each poll, so their
history has only a few points. The band syncs a reading every few minutes,
and the integration writes all of them as hourly mean/min/max to the long-term
statistics `mi_fitness:heart_rate_<user_id>` and `mi_fitness:spo2_<user_id>` —
including readings that arrive late, e.g. after the phone has not synced for a
while.

Steps go to `mi_fitness:steps_<user_id>` as an hourly cumulative sum. Use stat
type `change` for steps per day; the history fetched on the first poll (14 days)
shows up right away.

```yaml
type: statistics-graph
title: Heart rate – last 24 h
entities:
  - mi_fitness:heart_rate_1234567890
period: hour
days_to_show: 1
stat_types: [mean, min, max]
```

```yaml
type: statistics-graph
title: Steps per day
entities:
  - mi_fitness:steps_1234567890
period: day
days_to_show: 14
chart_type: bar
stat_types: [change]
```

## Privacy

No credentials or device identifiers are committed to this repository. Your
tokens are stored only in your own Home Assistant instance
(`.storage/core.config_entries`) — never commit your HA config.

## License

[MIT](LICENSE)
