# P3 provider/source-routing recall audit — 2026-08-29

## Scope

P3 investigates missed fresh controls in production run `33231413963` without
changing P4 regional-health viability semantics and without adding paid search
operations. Source artifact `9708618496` has SHA256
`b44c096424badb504e9e04be83db589f98cd80699ad4125cbedc051f0b6fe4e0` and was
produced by code SHA `ccacc65ee24a2a1159985c9a26b45bdb08002f6f`.

Effective window: `2026-08-27T04:43:51+03:00` →
`2026-08-29T05:16:40+03:00`.

Fixed controls:

1. Yandex Sim, first-party Yandex material dated 2026-08-28.
2. AI Alliance copyright/training-data policy: the Alliance letter is dated
   2026-08-27 and the Vedomosti material is dated 2026-08-28.
3. Tencent Hy4 preview, first-party Tencent release dated 2026-08-28; Reuters
   also covered the release that day.

P1/P2 are assumed merged. P3 does not revisit event freshness or Yandex Source
Pulse publication-date parsing.

## Reproduction from the saved production artifact

The deterministic fixture is
`automation/fixtures/recall/provider-routing-2026-08-29.json`. The pure-stdlib
replay/classifier is `automation/scripts/retrieval_routing_audit.py`.

Observed production routes:

| Route | Actual query | Source metadata | Control result |
| --- | --- | --- | --- |
| Primary Russia | `последние новости ИИ Яндекс Сбер VK МТС российский рынок` | 30 consulted URLs exposed | Yandex Sim absent; AI Alliance control absent |
| Primary legal | `latest major AI regulation copyright court rulings policy enforcement` | 42 consulted URLs exposed | AI Alliance control absent |
| Primary China models | `latest China Asia AI model releases agents open source` | 13 consulted URLs exposed | Tencent Hy3 surfaced, Hy4 control absent |
| Primary major agencies | `latest AI chips infrastructure financing earnings business deals policy security` | 18 consulted URLs exposed | Hy4 control absent |
| Reuters rescue v4 | `latest AI Russia chips infrastructure financing earnings business deals policy security` | `action.sources=null` | source pool is diagnostically unknown |
| Hybrid Russia health | `последние новости ИИ Россия модели продукты агенты инвестиции облако инфраструктура кибербезопасность регулирование` | 23 consulted URLs exposed | AI Alliance control absent |

The important distinction is before/after retrieval. For the six observations
where the provider exposed source metadata, the fixed control source never
entered the consulted source pool. Therefore those failures are classified as
`provider_source_pool_miss`, not post-retrieval normalization rejection. For the
Reuters v4 rescue, the completed search returned `action.sources=null`; the
correct classification is `source_metadata_unavailable`, not “Reuters consulted
zero sources”.

## Root cause

There is no evidence in the saved run that candidate normalization discarded
these three controls after successful retrieval. The stronger evidence points to
ranking/routing before candidate construction:

- the Russia product query had company anchors but no copyright/training-data
  surface;
- the China models guidance was broad, but the actual model-generated query
  dropped representative Tencent/Hunyuan anchors and the provider ranked an old
  Hy3 page instead of the fresh Hy4 release;
- the major-agencies query was weighted toward finance/infrastructure and omitted
  models/research, reducing the value of the publisher-filtered safety net for a
  major model release;
- v4 then converted the sole Reuters rescue slot from a global publisher route to
  a Russia-specific query because only the Russia Search-health gap was open.
  That regionalization cannot help a global China control such as Hy4 and spends
  the only Reuters opportunity on the already-covered regional dimension.

## P3 patch

### Primary Recall

No slot is added. The following existing passes receive explicit concise query
contracts:

- `major_agencies`: `latest AI models research chips infrastructure financing earnings business deals policy security`;
- `china_asia_models`: `latest China AI models releases Tencent Hunyuan Qwen DeepSeek GLM open source`;
- `russia`: `последние новости ИИ Россия Яндекс Сбер VK МТС продукты регулирование авторское право данные обучение моделей`.

These are representative ranking anchors, not company/publisher whitelists. All
existing guidance, domain-filter policy, source verification and one-search-per-
pass constraints remain intact.

### Agency discovery rescue v5

`agency_discovery_rescue_v4.py` remains preserved for replay. New v5 keeps the
single Reuters-only high-context search global:

`latest AI models research chips infrastructure financing earnings business deals policy security`

Regional gaps are recorded but no longer mutate the query. The search ceiling
remains one. v5 also distinguishes an absent/null `action.sources` field from a
present empty source list in its diagnostics.

### Hybrid

Trigger semantics stay exactly as v3: normal Hybrid maximum 4; only simultaneous
Search-derived Russia + China/Asia gaps may use the existing conditional fifth
Hybrid call. Only the text of already-triggered regional searches changes:

- Asia: `latest China AI models releases Tencent Hunyuan Qwen DeepSeek GLM Huawei products research`;
- Russia: `последние новости ИИ Россия Яндекс Сбер VK МТС продукты регулирование авторское право данные обучение моделей`.

No P4 viability/re-open logic is introduced here.

## Dependency and regression audit

### Search budget

Unchanged:

- Primary: 12;
- pre-Hybrid Reuters rescue: 1;
- Hybrid: 4 normally, 5 only on the already-approved double regional gap;
- Coverage: 7;
- ordinary whole-pipeline maximum: 24;
- double-gap maximum: 25;
- P3-added searches: 0.

### Contracts intentionally unchanged

- exact effective-window construction and 24-hour healing overlap;
- P1 Event Freshness Proof;
- P1 Source Freshness Proof ordering;
- P2 Source Pulse v1.3 Yandex date repair;
- candidate JSON schema and editorial ranking;
- archive dedupe;
- domain filters: only the existing publisher-specific passes use them;
- Coverage directions and Coverage paid-search ceiling;
- P4 regional-health viability semantics remain deferred;
- no publication quota for Russia/China.

### Compatibility

- `agency_discovery_rescue_v4.py` remains unchanged as a replay/rollback asset;
- v5 is selected only by the stable Hybrid entrypoint;
- preserved Hybrid v2/v3 files are not rewritten; the stable wrapper overlays
  the P3 regional query text at runtime;
- existing `24/25` constants remain guarded by regression tests.

## Offline experiment result

`retrieval_routing_audit.py` must report:

- six `provider_source_pool_miss` observations;
- one `source_metadata_unavailable` observation;
- all three fixed controls covered by at least one proposed query route;
- ordinary maximum 24, double-gap maximum 25, P3 additional searches 0.

This is a deterministic structural experiment. It proves the location of the
saved-run misses and that the new query contracts cover the missing semantic
surfaces without increasing budget. It does **not** claim that a fresh hosted
provider/Terra ranking experiment was run. No Terra-specific assistant tool is
available in this session, and no paid production/OpenAI search was spent for P3
diagnosis. Provider-level recall improvement therefore remains an empirical
production observation to monitor after merge, while the deterministic routing
and budget invariants are testable before merge.
