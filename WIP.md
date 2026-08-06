# WIP - bluetape4k-dependencies

Snapshot: 2026-08-06 KST
Scope: dependencies 1.4.0 최종 배포 및 1.5.0 개발선 후속 전환.
Milestone: 1.4.0, 2 open issues (#168 and #171).

## 현재 방향

`bluetape4k-dependencies:1.4.0`은 조정된 stable release train의 마지막
BOM이다. 선행 라이브러리 8개는 모두 signed tag, release workflow, Maven
Central publication, GitHub Release 검증을 마쳤다. 최종 catalog는
`catalog/2026-08-06-03`으로 서명됐고 merge commit
`3d2fb6e0087a6bbef5418aee8024bba9dd527e26`으로 고정됐다.

9개 관리 저장소는 checked-in settings와 CI를 동일한 immutable catalog
commit으로 이관했다. 8개 배포 저장소의 수동 release dispatch 변수는 signed
catalog tag를 참조하며, `bluetape4k-experimental`은 catalog-only consumer로만
유지한다. `bluetape4k-workshop`과 예제 저장소는 이 release train에서 제외한다.

## 완료된 이관

| Repository | Stable version | Release HEAD | Catalog follow-up PR | Follow-up merge |
|---|---:|---|---:|---|
| `bluetape4k-projects` | `1.12.1` | `7cf0b736` | #1317 | `dd450d84` |
| `bluetape4k-aws` | `0.5.0` | `664e4dfb` | #444 | `e045f648` |
| `bluetape4k-experimental` | catalog-only | `57b7f578` | #88 | `ea0f6533` |
| `bluetape4k-exposed` | `1.12.1` | `4cc2cce0` | #622 | `86eb2003` |
| `bluetape4k-graph` | `0.6.0` | `72c0256e` | #453 | `5cfc95ad` |
| `bluetape4k-image` | `0.4.0` | `9961d45d` | #469 | `d937c088` |
| `bluetape4k-javers` | `0.3.0` | `978d0490` | #295 | `2cf499e6` |
| `bluetape4k-leader` | `0.5.0` | `721a9a38` | #655 | `797ce8f5` |
| `bluetape4k-text` | `0.3.0` | `aead213d` | #231 | `bd960458` |

모든 follow-up PR은 exact-head CI, mergeability, review thread 검증 후
병합됐다. 다음 개발 버전은 Projects/Exposed `1.13.0`, AWS/Leader `0.6.0`,
Graph `0.7.0`, Image `0.5.0`, Javers/Text `0.4.0`으로 전환됐다.

## 최종 배포 증거

- Catalog PR #173 exact-head CI와 post-merge CI: PASS.
- Signed catalog tag: GitHub verification `valid`, exact merge로 peel 확인.
- 중앙 catalog governance: 168 aliases, 8 sub-BOMs, adoption/Dependabot sync PASS.
- 병합된 default head publication contract: 9 repositories, 173 POMs,
  45,211 dependency entries, 173 Maven effective models, failures 0.
- 생성된 `1.4.0` POM: 77 dependency-management entries, missing version 0,
  SNAPSHOT 0, imported BOM 18개, SHA-256 `d6b4305d5fba5ec960532b34864254fd9ed844cb67adbecff1d00eca8f0eb967`.

## 남은 우선순위

1. 이 release 문서 변경의 exact-head PR CI를 통과하고 병합한다.
2. 병합 commit에 signed tag `1.4.0`을 생성해 tag-triggered release를 실행한다.
3. Maven Central BOM POM/module, imported BOM, Central-only consumer와 GitHub
   Release를 검증한다.
4. issue #168/#171, milestone `1.4.0`, Type P receipt를 완료한다.
5. `baseVersion=1.5.0` 후속 PR을 병합하고 안전한 worktree cleanup을 수행한다.

## WIP 제한

| Lane | Limit | Current next |
|---|---:|---|
| Stable publication | 1 | `dependencies 1.4.0` release PR/CI/tag/publication만 진행한다. |
| Follow-up versioning | 0 | public Central 검증 전에는 `1.5.0` 변경을 시작하지 않는다. |
| Cleanup | 0 | merge와 receipt 완료가 증명된 worktree만 정리한다. |
