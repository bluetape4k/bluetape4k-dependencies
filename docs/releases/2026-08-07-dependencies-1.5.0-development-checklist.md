# bluetape4k-dependencies 1.5.0 개발 train 체크리스트

상태: **진행 중 / 스냅샷 train**
대상 라인: `1.5.0-SNAPSHOT`
안정 버전 게시 대상: `1.5.0` (이 체크리스트로는 권한을 부여하지 않음)
최근 확인된 안정 버전: `1.4.0`
릴리스 권한: 사용자가 2026-08-07에 승인된 1.4.0 이후 작업의 계속을
명시적으로 요청했다. 이 체크리스트는 스냅샷 검증만 승인하며 안정 tag,
GitHub Release 또는 Maven Central 안정 버전 게시를 승인하지 않는다.

## 범위와 경계

- 중앙 source of truth: `bluetape4k-dependencies` `develop`의
  `1d23b2386ea68ada57eff349fc2e9383eb279706`.
- 현재 catalog 계약: 동일한 develop head의 `gradle/libs.versions.toml`이다.
  새 catalog train이 승인될 때까지 안정 소비자는 변경 불가능한 catalog tag
  `catalog/2026-08-06-03`를 계속 고정한다.
- 게시된 BOM 스냅샷: `bluetape4k-dependencies:1.5.0-SNAPSHOT`.
- 게시 library 스냅샷 범위: Projects, AWS, Exposed, Graph, Image, Javers,
  Leader, Text. Experimental은 catalog 전용으로 남긴다.
- 명시적 제외: `bluetape4k-workshop`, 모든 workshop, example 및 application
  repository.
- 안정 버전 1.4.0의 artifact, tag, GitHub Release, source manual,
  `bluetape4k.github.io`는 과거 게시가 완료된 상태이므로 tag를 다시 만들거나
  덮어쓰지 않는다.

## 고정한 개발 head

| Repository | Development version | Exact `develop` head | Snapshot status |
|---|---:|---|---|
| bluetape4k-dependencies | `1.5.0-SNAPSHOT` | `1d23b2386ea68ada57eff349fc2e9383eb279706` | Metadata HTTP 200; build 1 |
| bluetape4k-projects | `1.13.0-SNAPSHOT` | `ffde7b8be16124b1c538bb318a7d482927f738ad` | Exact-head Nightly/publish; metadata HTTP 200; build 2 |
| bluetape4k-aws | `0.6.0-SNAPSHOT` | `76f9caed95263acef6f6143ded9519264b88c853` | Exact-head Nightly/publish; metadata HTTP 200; build 2 |
| bluetape4k-exposed | `1.13.0-SNAPSHOT` | `6bff7d9939243d166e212ce840ee90261e7239c7` | Exact-head Nightly/publish; metadata HTTP 200; build 2 |
| bluetape4k-graph | `0.7.0-SNAPSHOT` | `f29ddc29f5b59a82f218b9f815046fac288ecd30` | Exact-head Nightly/publish; metadata HTTP 200; build 2 |
| bluetape4k-image | `0.5.0-SNAPSHOT` | `e56fea655ad3168527b5f663d114df722ad55d3f` | Full Nightly/publish repaired; metadata HTTP 200; build 1 |
| bluetape4k-javers | `0.4.0-SNAPSHOT` | `fb279cdba663bde80d9b146049aca146433a9b36` | Exact-head Nightly/publish; metadata HTTP 200; build 2 |
| bluetape4k-leader | `0.6.0-SNAPSHOT` | `5a4837e374df53c5a2c272b7a1d883f07abda6ae` | Exact-head Nightly/publish; metadata HTTP 200; build 2 |
| bluetape4k-text | `0.4.0-SNAPSHOT` | `c5726bea30591e4c5c26523ccac4ad62c5ea9237` | Exact-head Nightly/publish; metadata HTTP 200; build 2 |

## 순서가 있는 gate

- [x] **PUB-01 / REL-01 — Pin target inventory and authority.**
  대상은 1.5.0 개발 스냅샷 라인이며 안정 버전 게시 범위는 이 체크리스트
  밖에 있다. Workshop 범위는 명시적으로 제외한다.
- [x] **PUB-02 / REL-02 — Query live topology and planning state.**
  게시 대상 library 8개와 dependencies가 publisher inventory다. Experimental은
  catalog 전용이며 workshop/example repository는 제외한다.
- [x] **PUB-03 / REL-03 — Establish the exact candidate state.**
  Image 스냅샷을 복구한 뒤 중앙 catalog 검사와 publication-POM gate를 통과했다.
- [x] **PUB-06 — Complete the Image snapshot gate.**
  Full Nightly `31175781034`와 publish `31176250467`가 정확한
  `develop` head; `bluetape4k-image-bom:0.5.0-SNAPSHOT` metadata is HTTP 200
  (`lastUpdated=20260807120023`, build 1). All required OCR and VIPS jobs ran.
- [x] **PUB-08 — Verify all downstream snapshots.**
  library repository 8곳 모두 exact-head Nightly와 workflow-run publication을
  통과했다. 범위에 포함된 BOM metadata 9건은 모두 HTTP 200이며, 갱신된
  downstream record는 복구한 Image record(build 1)를 제외하고 build 2다.
- [x] **PUB-09 — Re-run catalog and publication-POM validation.**
  필수 명령은 `sync-managed-catalog`, `sync-shared-versions`,
  `sync-dependabot-ignores`, and `verify-publication-poms.py --workspace ..`;
  all passed, including `failures=0`, `repositories=9`, `files=173`,
  `dependencies=45211`, and `maven_models=173`.
- [x] **PUB-10 — Complete post-release cleanup.**
  연결된 worktree와 GitHub milestone/issue/Dependabot 후속 상태를 감사한다.
  안전하게 제거할 worktree 후보는 없었으므로 dirty, detached, ambiguous,
  unmerged branch를 보존했다. 비어 있는 과거 release milestone 7개를 닫았고
  backlog/current milestone과 열린 issue/PR은 유지했다.
- [x] **PUB-11 — Prepare the next stable release gate.**
  최종 스냅샷 matrix를 기록하고 `1.5.0` tag 또는 안정 버전 게시 전에
  별도로 승인된 안정 release checklist를 만든다.

## 현재 evidence와 복구

- Dependencies snapshot workflow: run `31084129721`, exact head
  `1d23b2386ea68ada57eff349fc2e9383eb279706`, successful.
- Image recovery: Nightly `31175781034` and publish `31176250467` passed at
  `e56fea655ad3168527b5f663d114df722ad55d3f`.
- Exact-head refresh runs: Projects `31177226943`/`31178898628`, AWS
  `31177229239`/`31177844933`, Exposed `31177231582`/`31178860395`, Graph
  `31177233756`/`31177779183`, Javers `31177236072`/`31178149238`, Leader
  `31177238325`/`31178660581`, and Text `31177240333`/`31177822624`.
- Central gates: managed catalog `168 aliases / 8 sub-BOMs`, shared-version
  adoption clean, Dependabot ignore sync clean, and publication-POM gate
  `173 POMs / 45,211 dependency entries / 173 Maven models / failures 0`.
- 이전 스냅샷 head의 차이는 `docs/manual/**`와 `scripts/manual/**` 아래에만
  있었지만, waiver 없이 스냅샷 gate를 충족하기 위해 library 7곳을 현재
  exact `develop` SHA에서 다시 갱신했다.
- 복구 규칙: 이후 명시적인 release 결정으로 gate가 바뀌지 않는 한
  `override_full_validation`을 사용하지 않는다. Image 복구에는 full Nightly와
  validation-run-id publication을 사용했다.

## 정리와 안정 버전 인계

- Historical empty milestones closed: dependencies `1.3.0`/`1.3.1`, Projects
  `1.12.0`/`1.12.1`, and Text `0.1.1`/`0.1.2`/`0.1.3`.
- 현재 catalog 소비자는 변경 불가능한 commit
  `catalog/2026-08-06-03` (`3d2fb6e0087a6bbef5418aee8024bba9dd527e26`); no new
  catalog tag is needed because this development-line commit changes only the
  BOM version and release bookkeeping, not shared dependency refs.
- 별도 안정 버전 hold 문서:
  `docs/releases/2026-08-07-dependencies-1.5.0-release-checklist.md`.
- 안정 `1.5.0` tag, GitHub Release, Maven Central publication은 이 개발
  체크리스트로 권한을 부여하지 않는다.

## 중단 조건

이 체크리스트는 개발 스냅샷 train에 대해서는 완료된 상태다. 별도 안정
체크리스트는 hold 문서일 뿐이다. exact-head CI/review, catalog 결정, 최신
게시 권한 gate가 승인될 때까지 `1.5.0` 안정 tag, GitHub Release 또는 안정
Maven 게시를 만들지 않는다.
