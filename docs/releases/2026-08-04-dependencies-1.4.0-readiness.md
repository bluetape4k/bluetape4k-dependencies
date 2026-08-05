# dependencies 1.4.0 배포 준비 상태

## 결론

`bluetape4k-dependencies:1.4.0`의 외부 의존성 최신 호환 버전 통일과 로컬
소비자 검증은 완료했다. 다만 현재 생성되는 `1.4.0` POM이 아직 8개의 내부
`*-SNAPSHOT` BOM을 import하고, 대응하는 안정 버전 POM은 Maven Central에서 모두
HTTP 404다. 따라서 현재 상태는 **PENDING**이며 tag, workflow dispatch, publication을
실행할 수 없다.

## 고정된 후보

| 항목 | 값 |
|---|---|
| dependencies candidate HEAD | `188f27c012801e011c416ee4e0cfded9294293d9` |
| catalog source commit | `fbb6df78d04fcb9d7252ce0a1338ee67af9fa817` |
| catalog SHA-256 | `9c9469f516e818dd4c0503babaff182613d7994b109441e78acf3bc4842c25df` |
| audit 범위 | 509 authorities / 543 compatibility lines |
| 채택 delta | 121 version keys / 130 authorities |
| resolved graph | 260 exact before/after observations, failures 0 |
| downstream full build | 9 library repositories, failures 0 |
| publication POM gate | 175 POMs / 175 effective models / failures 0 |

resolved graph의 source-controlled receipt는
[`2026-08-05-issue-169-exhaustive-resolved-graphs.json`](2026-08-05-issue-169-exhaustive-resolved-graphs.json)이며,
SHA-256은 `1f019f350fa9c52c82f0152f2dd517fed55d93be354123b46df0d017f63d7c97`다.
각 authority를 독립 Gradle configuration으로 분리해 baseline과 candidate 버전을
정확히 요청하고, 실제 선택 버전, 전체 component 목록과 graph hash, before/after
added/removed component delta를 기록했다. 실행 전에 현재 catalog bytes와 checksum
sidecar, ledger candidate SHA, 121개 candidate version을 상호 검증하고, 전이 artifact
하나라도 resolve되지 않으면 실패한다.
9개 downstream exact HEAD와 full-build/POM 로그 hash는
[`2026-08-05-issue-169-full-candidate-receipt.json`](2026-08-05-issue-169-full-candidate-receipt.json)에
고정했다.

## 안정 배포 DAG

```text
projects 1.12.0
  ├─ exposed 1.12.0 ─┬─ aws 0.5.0
  │                  └─ leader 0.5.0
  ├─ image 0.4.0
  ├─ text 0.3.0
  ├─ graph 0.6.0
  └─ javers 0.3.0
            ↓
stable catalog ref + downstream/POM 재검증
            ↓
dependencies 1.4.0
```

`bluetape4k-workshop`과 예제 저장소는 안정 배포 train에서 제외한다.
`bluetape4k-experimental`은 catalog 소비자 검증에만 포함하며 공개 BOM 선행 배포
대상이 아니다.

## upstream preflight

| Repository | Target | Exact candidate HEAD | Stable POM | 판정 |
|---|---:|---|---:|---|
| projects | `1.12.0` | `66fe47d3` | 404 | PENDING |
| exposed | `1.12.0` | `16a8fed2` | 404 | PENDING |
| image | `0.4.0` | `295c7228` | 404 | PENDING |
| text | `0.3.0` | `dedfb886` | 404 | PENDING |
| graph | `0.6.0` | `95677bb7` | 404 | PENDING |
| javers | `0.3.0` | `6ac3b824` | 404 | PENDING |
| aws | `0.5.0` | `7584c2f3` | 404 | PENDING |
| leader | `0.5.0` | `7f6bcc51` | 404 | PENDING |

모든 후보 worktree는 clean하고 local HEAD가 origin과 일치한다. 그러나 exact 후보
SHA의 full CI/Nightly/Snapshot 증거는 없거나 dependency submission만 존재한다.
기존 develop Nightly 성공은 SHA가 달라 대체 증거로 사용할 수 없다.

문서 차단도 남아 있다. projects는 `1.12.0 — Unreleased`이고 release 문서 PR
`#1310`이 열려 있다. image는 `0.4.0 - TBD`, graph는 `[Unreleased]`, leader는
`0.5.0 — 미공개`, javers/text도 미공개·미배포 상태다. AWS WIP도 현재 merge 상태와
맞지 않는다. Javers `#292`, Text `#229` 등 release workflow를 변경하는 open PR은
배포 전 명시적으로 merge, close, 또는 waiver 처리해야 한다.

## 현재 POM 차단

`generatePomFileForBluetapeDependenciesPublication`은 성공하지만 결과 POM에는 다음
8개 snapshot import가 남는다.

- `bluetape4k-bom:1.12.0-SNAPSHOT`
- `bluetape4k-aws-bom:0.5.0-SNAPSHOT`
- `bluetape4k-image-bom:0.4.0-SNAPSHOT`
- `bluetape4k-text-bom:0.3.0-SNAPSHOT`
- `bluetape4k-graph-bom:0.6.0-SNAPSHOT`
- `bluetape4k-leader-bom:0.5.0-SNAPSHOT`
- `bluetape4k-exposed-bom:1.12.0-SNAPSHOT`
- `bluetape4k-javers-bom:0.3.0-SNAPSHOT`

snapshot metadata는 모두 존재하지만 안정 POM은 모두 404다. 안정 upstream 공개
전에는 단순히 `-SNAPSHOT` 문자열만 제거하지 않는다. 먼저 각 BOM을 실제로 배포해
HTTP 200을 확인한 다음 catalog를 안정 버전으로 전환하고 전체 POM/effective-model,
downstream build, resolved-graph 검증을 다시 수행해야 한다.

## 남은 배포 게이트

1. 각 upstream의 changelog/WIP와 release-affecting PR 상태 정리
2. exact candidate의 full CI/Nightly 및 publication POM 검증
3. dependency DAG 순서대로 semver tag와 stable BOM 배포
4. 각 target stable POM의 Maven Central HTTP 200 확인
5. central catalog의 8개 BOM ref를 stable로 변경하고 새 catalog train ref 고정
6. downstream full build, 175 POM/effective-model, resolved graph 재검증
7. dependencies open PR/issue 및 changelog/release checklist 정리
8. exact final HEAD, CI, credentials, workflow inputs를 재확인한 뒤 별도 승인
9. `1.4.0` tag와 release workflow dispatch, Maven Central/GitHub Release 검증

위 조건이 충족되기 전에는 catalog tag, semver tag, workflow dispatch, publication,
release, merge, milestone 종료를 수행하지 않는다.
