# WIP - bluetape4k-dependencies

Snapshot: 2026-08-12 KST
Scope: dependencies 1.5.0 개발선.

## 2026-08-12 게시 후속 보강

안정 게시 후 다음 개발선이 `baseVersion` 변경만으로 끝나지 않도록 중앙
catalog의 8개 내부 BOM ref를 각 `baseVersion + -SNAPSHOT`으로 정렬하고,
`config/post-publish-next-development-line.json` 및
`scripts/verify-post-publish-next-development-line.py`로 fail-closed 검증을
추가했다. 소스의 `snapshotVersion=`은 계속 비워 두며 snapshot workflow가
`-PsnapshotVersion=-SNAPSHOT`을 runtime에 주입한다.

기준선 점검에서 발견한 이미 커밋된 `bluetape4k-graph-io-micrometer` 모듈의
생성 catalog 누락도 같은 격리 작업트리에서 복구했다. 생성기 검증 결과는
`aliases=169`, `sub-boms=8`이다.

snapshot publication 검증은 preflight와 post-publication metadata 확인을
분리했다. 첫 snapshot이 아직 없을 때도 publication을 시작할 수 있고, publish
직후에만 `--require-artifacts`를 요구한다. stable `main` CI는 개발선 검증을
건너뛰고 release workflow의 stable boundary guard를 사용한다.

이번 일회성 JDK 25 전환을 위해 `exposed-r2dbc-workshop`,
`exposed-workshop`, `timefold-workshop`의 JDK25 worktree workflow를 25로
정렬하고, `bluetape4k-workshop`에는 별도 `chore/jdk25-workflows`
worktree를 만들었다. 원격 반영과 PR/merge는 별도 전달 gate다.

현재 중앙 변경은 격리된 `chore/publish-next-line-jdk25`의
`45235aa22184b6a2280f530fb90c82a94e31c59d`에 커밋되어 있다. 새 immutable
catalog train ref를 원격에 공개하고 downstream settings ref를 갱신하는 일,
push/PR/merge/publication은 별도 전달 gate다. `.java-version` 21 -> 25 변경은
모든 1차 repository root의 다른 검증이 끝난 뒤 마지막 mutation으로 수행했고,
각 JDK25 격리 branch에도 로컬 커밋했다.

## 현재 상태

`bluetape4k-dependencies:1.4.0` 안정 배포 train은 완료됐다. 선행 라이브러리
8개, 최종 catalog `catalog/2026-08-06-03`, dependencies BOM, GitHub Release,
Maven Central metadata와 Central-only consumer를 모두 검증했다. issue #168과
#171 및 milestone `1.4.0`도 최종 증거와 함께 닫았다.

현재 개발 버전은 `1.5.0`이다. `snapshotVersion`은 비워 두며, 다음 catalog
train이 승인되기 전에는 새로운 stable tag나 publication을 만들지 않는다.

## 1.4.0 완료 증거

- Release PR #174 merge: `8a738f084de98323b5651c548b9d2c354fb22329`.
- PR CI `31079582802`, post-merge CI `31080318880`: PASS.
- GitHub-valid signed tag: `1.4.0`, exact merge로 peel 확인.
- Publish Release run `31081143359`: PASS.
- Maven Central POM/module: HTTP 200.
- 공개 POM: 77 dependency-management entries, 18 imported BOMs,
  missing version 0, SNAPSHOT 0, SHA-256
  `d6b4305d5fba5ec960532b34864254fd9ed844cb67adbecff1d00eca8f0eb967`.
- Central-only consumer: 8개 대표 Bluetape 모듈의 versionless resolution PASS.
- Type P receipt: `20260806T074128Z-5d92140b`, sequence 14, checksum
  `733c25592a3d02437e1b0686769cf93152b30c3c1c78035628389a1d7161c69c`.

## 다음 우선순위

1. 외부 dependency/plugin 변경은 중앙 catalog authority와 delta receipt를 먼저
   갱신한다.
2. 관리 저장소는 immutable catalog ref를 사용하고, 예외가 필요한 경우에만
   명시적 authority record를 추가한다.
3. 다음 stable train은 새 release checklist와 explicit publication authority를
   확보한 뒤 시작한다.

`bluetape4k-workshop`과 예제/application 저장소는 stable publication scope에서
계속 제외한다. `bluetape4k-experimental`은 catalog-only consumer로 유지한다.
