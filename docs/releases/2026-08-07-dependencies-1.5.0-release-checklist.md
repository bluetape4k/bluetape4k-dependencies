# bluetape4k-dependencies 1.5.0 안정 release 체크리스트

상태: **보류 / 게시 권한 없음**
대상: `bluetape4k-dependencies` BOM `1.5.0`
최근 안정 버전: `1.4.0`
개발 스냅샷 evidence: `docs/releases/2026-08-07-dependencies-1.5.0-development-checklist.md`

## Release 경계

- 안정 버전 게시 권한은 이 문서로 부여하지 않는다. 다음 명시적 release
  결정을 위한 준비 artifact다.
- 게시된 스냅샷 train은 dependencies와 Projects, AWS, Exposed, Graph, Image,
  Javers, Leader, Text를 포함한다. Workshop/example/application repository는
  제외하고 Experimental은 catalog 전용으로 남긴다.
- 기존 안정 catalog 소비자는 다음 dependency 변경 train에서 새 catalog tag를
  입증하고 승인할 때까지 변경 불가능한 catalog commit
  `catalog/2026-08-06-03` (`3d2fb6e0087a6bbef5418aee8024bba9dd527e26`) until a
  future dependency-change train proves and approves a new catalog tag.

## 안정 버전 side effect 전 필수 gate

- [ ] Fresh exact `develop` SHA inventory and release authority.
- [ ] Fresh PR/review/CI proof for the release commit and release checklist.
- [ ] Stable candidate POM and effective-model validation for all publishers.
- [ ] Stable-equivalent snapshot proof with no source/catalog drift.
- [ ] Fresh tag/release absence and declared workflow-input audit.
- [ ] Explicit user approval for tag creation, Maven Central publication, and
  GitHub Release. These are separate gates.
- [ ] Post-publication Central POM, checksum, release, catalog, manual, and site
  verification followed by a new next-version development checklist.

## 현재 evidence 기준선

- Dependencies `1.5.0-SNAPSHOT` metadata: HTTP 200, build 1.
- All eight library snapshot lines have exact-head Nightly and publication
  success; all nine BOM metadata records are HTTP 200.
- Central catalog/POM validation is clean: 168 aliases, 8 sub-BOMs, and
  `failures=0`, `repositories=9`, `files=173`, `dependencies=45211`,
  `maven_models=173`.
- 위의 모든 필수 gate를 최신 상태로 다시 확인하기 전에는 안정 `1.5.0` tag,
  GitHub Release 또는 안정 버전 게시를 만들 수 없다.

## 중단 조건

확인하지 않은 gate가 모두 최신 PASS가 되고 각각의 되돌릴 수 없는 안정 버전
side effect에 대해 별도 명시적 승인이 내려질 때까지 보류 상태를 유지한다.
