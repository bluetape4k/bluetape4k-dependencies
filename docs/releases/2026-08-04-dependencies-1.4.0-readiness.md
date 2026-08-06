# dependencies 1.4.0 배포 준비 상태

## 결론

`bluetape4k-dependencies:1.4.0`의 선행 라이브러리 배포와 최종 안정 catalog
후보 검증을 완료했다. 8개 공개 BOM은 모두 Maven Central에서 조회되고, 최종
catalog에는 Bluetape SNAPSHOT import가 없다. exact catalog SHA에서 9개 downstream
full build, 173개 publication POM/effective-model, 143개 resolved-graph spec과 286개
observation이 모두 통과했다.

현재 상태는 **CATALOG READY**다. 남은 순서는 최종 catalog PR의 exact-head CI,
merge, 서명 tag `catalog/2026-08-06-03`을 완료한 뒤, 그 merge head에서
`dependencies 1.4.0` release PR/CI와 서명 tag 및 publication을 수행하는 것이다.

## 고정된 최종 후보

| 항목 | 값 |
|---|---|
| immutable candidate commit | `03eb9fe120670e55c77bee998dc318df8184c755` |
| catalog SHA-256 | `6c52b7f09e28de2e8b23462d05819c09cb33fe9bf42762f1f97216a8b78dea34` |
| audit 범위 | 512 authorities / 546 compatibility lines |
| 외부 version delta | 123 version keys |
| resolved graph | 143 specs / 286 observations / failures 0 |
| downstream full build | 9 repositories / failures 0 |
| publication POM gate | 173 POMs / 173 effective models / failures 0 |
| Maven dependency entries | 45,211 |

resolved graph의 source-controlled receipt는
[`2026-08-05-issue-169-exhaustive-resolved-graphs.json`](2026-08-05-issue-169-exhaustive-resolved-graphs.json)이며
SHA-256은 `2b1735f5684aa7eb843d91237dae38edf613dc0485d9550537bfe9312ab5652c`다.
9개 downstream exact HEAD와 full-build/POM 증적은
[`2026-08-05-issue-169-full-candidate-receipt.json`](2026-08-05-issue-169-full-candidate-receipt.json)에
고정했으며 SHA-256은
`37f66a1a99f48c0be27f697625c06eb2240d023f4b487cb2d36df47c07d24a1c`다.

## 공개 upstream 상태

| Repository | Version | Exact release HEAD | Maven Central | 판정 |
|---|---:|---|---:|---|
| projects | `1.12.1` | `7cf0b736` | 75 publications | PASS |
| exposed | `1.12.1` | `4cc2cce0` | 35 publications | PASS |
| image | `0.4.0` | `9961d45d` | 11 publications | PASS |
| text | `0.3.0` | `aead213d` | 6 publications | PASS |
| graph | `0.6.0` | `72c0256e` | 15 publications | PASS |
| javers | `0.3.0` | `978d0490` | 7 publications | PASS |
| aws | `0.5.0` | `664e4dfb` | 6 publications | PASS |
| leader | `0.5.0` | `721a9a38` | 17 publications | PASS |

각 release tag는 exact merge HEAD를 가리키는 서명 tag이며, release workflow와
GitHub Release가 성공했다. 모든 stable BOM POM과 Gradle module metadata가 공개됐고,
AWS/Javers/Leader 30개 component의 Maven Central-only versionless consumer도 통과했다.

## 최종 catalog 검증

- `bluetape4k-aws-bom=0.5.0`
- `bluetape4k-javers-bom=0.3.0`
- `bluetape4k-leader-bom=0.5.0`
- 나머지 5개 공개 BOM도 모두 위 표의 stable version으로 고정됐다.
- catalog checksum sidecar와 실제 bytes가 일치한다.
- 512개 authority metadata 중 507개 stable metadata와 5개 preview-only line을
  정책대로 검증했고 metadata-unavailable은 0이다.
- central catalog adoption, managed catalog 168 aliases/8 sub-BOMs, downstream
  Dependabot ignore가 strict repository map에서 통과했다.
- 9개 downstream full build가 exact release HEAD와 동일 catalog SHA에서 통과했다.
- Projects의 최초 병렬 실행에서 Elasticsearch/Pulsar Testcontainers timeout이
  발생했으나 두 targeted test가 통과했고, `--max-workers=2` full build 1,019 tasks가
  성공해 catalog 회귀가 아님을 확인했다.
- 9개 publisher와 dependencies BOM을 포함한 173개 POM 및 173개 Maven effective
  model이 통과했으며 versionless dependency-management entry는 없다.

`bluetape4k-workshop`과 예제/application 저장소는 안정 배포 train에서 제외한다.
`bluetape4k-experimental`은 catalog-only downstream 검증에는 포함하지만 공개 BOM
배포 대상은 아니다.

## 남은 배포 게이트

1. 최종 catalog PR exact-head CI와 mergeability를 확인하고 merge한다.
2. merge head에 서명 tag `catalog/2026-08-06-03`을 생성하고 signature/peeled commit을 검증한다.
3. downstream이 선언한 catalog ref를 최종 tag로 이관한다.
4. `dependencies 1.4.0` release head의 stable-only POM, CI, workflow input을 재검증한다.
5. 서명 tag `1.4.0`을 생성해 Publish Release workflow를 실행한다.
6. Maven Central BOM POM/module, imported BOM 전부의 stable/public 상태와
   Central-only consumer, GitHub Release를 확인한다.
7. issue #171, milestone `1.4.0`, Type P receipt, 다음 개발 버전과 안전 cleanup을 마감한다.

최종 catalog tag 또는 `1.4.0` tag는 각 단계 직전 exact head와 live GitHub 상태를
다시 확인한 후에만 생성한다.
