# bluetape4k 2.2.0 개발선 체크리스트

상태: **진행 중 / 하위 snapshot 선행 공개 대기**

## 고정 입력

- 안정 기준: `bluetape4k-dependencies:2.1.0`, Projects/Exposed `2.1.0`,
  AWS/Graph/Image/JaVers/Leader/Text `1.1.0`
- 다음 중앙 개발선: `bluetape4k-dependencies:2.2.0-SNAPSHOT`
- 다음 내부 BOM: Projects/Exposed `2.2.0-SNAPSHOT`, 나머지 publisher
  `1.2.0-SNAPSHOT`
- 공통 snapshot catalog commit: `7a5995fd46031ce1faf16337fa08d954436f8f9a`
  (`catalog/2026-11-22-01`, tag object
  `f2f53729ee7007bb40adf1ed892a9c160a03ec2e`)
- 공식 release consumer: `bluetape4k-dependencies:2.1.0`과 안정 catalog
  `1669b069690864be8a19a67598e9ac9db807f9f5` 유지

## 의존성 순서

중앙 BOM은 내부 하위 BOM을 import하므로 중앙 snapshot을 먼저 공개하지
않습니다. 다음 순서를 지킵니다.

1. `bluetape4k-projects` `2.2.0-SNAPSHOT`
2. Projects snapshot을 확인한 뒤 `bluetape4k-exposed` `2.2.0-SNAPSHOT`
3. AWS, Graph, Image, JaVers, Leader, Text `1.2.0-SNAPSHOT`을 각 publisher의
   dependency edge에 따라 순차 공개
4. 8개 하위 BOM의 Central metadata/POM/Gradle Module Metadata를 모두 확인
5. 하위 BOM을 import하는 중앙 `bluetape4k-dependencies:2.2.0-SNAPSHOT`
   공개
6. `verify-post-publish-next-development-line.py --require-artifacts`, 전체
   publication-POM gate, downstream smoke를 재실행

순서가 바뀌면 이후 POM/CI 증거를 폐기하고 최초 실패한 predecessor부터
재검증합니다. 중앙 BOM을 먼저 공개해 미게시 하위 snapshot을 가리키는 우회는
허용하지 않습니다.

## PR 및 검증 상태

| 저장소 | PR | exact head | 상태 |
|---|---:|---|---|
| Projects | #1914 | `96663caae7bd69ed33d15f418bb6d6c76a010ab9` | CI green, merge-ready |
| AWS | #687 | `23b194d85539a6213bf3e8f1dd8989d9d651868f` | snapshot predecessor 대기 |
| Exposed | #939 | `352d0d28cafa6559875b5418f7247d26605b0c8b` | Projects snapshot 대기 |
| Graph | #667 | `d1d35342dffffc095412f79a0b2352cc74c9f06e` | Projects snapshot 대기 |
| Image | #713 | `a2d740b3dca39bead7328ea3f825e6a03b25d262` | Projects snapshot 대기 |
| JaVers | #404 | `3eb8191e9ce64041be4bcdfa0d35942f31e1fd0a` | snapshot predecessor 대기 |
| Leader | #1020 | `b25f9d221c59059f18a94d0f1123680790f19982` | snapshot predecessor 대기 |
| Text | #353 | `d7e62b339937e6a443271746002853c30a7764a5` | snapshot predecessor 대기 |
| Dependencies | #291 | `c5c5c1dacb94071db52f2d105014b42e6102ca36` | 하위 snapshot 공개 후 재검증 |

## 현재 증거와 정지 조건

- `scripts/verify-post-publish-next-development-line.py --summary`는
  `8 publishers`, `9 snapshot libraries`, `5 official-release examples`,
  `0 development-snapshot examples`를 확인했습니다.
- 개발선/CI 계약 회귀 테스트 47개가 통과했습니다.
- Projects #1914는 exact head에서 required CI가 모두 성공하고
  `mergeStateStatus=CLEAN`입니다.
- Dependencies #291의 현재 Build BOM 및 Cross-repository POM 실패는
  `2.2.0-SNAPSHOT` 중앙 BOM이 아직 공개되지 않은 선행 상태 부족입니다.
  이를 우회하거나 실패를 green으로 해석하지 않습니다.
- 각 merge는 해당 exact head의 fresh CI/review/thread/mergeability를 다시
  읽은 뒤 별도 병합 게이트로 처리합니다.

## DoD

- [x] 안정 release 후 source `baseVersion`과 빈 `snapshotVersion` 계약 고정
- [x] 내부 snapshot catalog와 공식 release consumer 경계 고정
- [x] 문서에 하위 publisher → 중앙 BOM 순서 명시
- [x] 개발선 verifier 및 targeted governance tests 통과
- [ ] Projects snapshot 공개 및 Central metadata 확인
- [ ] 나머지 7개 child snapshot 공개 및 Central metadata 확인
- [ ] 중앙 `2.2.0-SNAPSHOT` 공개 및 `--require-artifacts` 통과
- [ ] publication-POM 전수 재검증과 downstream smoke

최종 상태: `PENDING` — 선행 publisher snapshot 공개와 이후 중앙 BOM
publication이 남아 있습니다.
