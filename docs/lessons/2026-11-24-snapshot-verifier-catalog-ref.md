# Snapshot verifier의 catalog ref를 consumer와 일치시킨다

## 상황

Dependencies `2.1.0` 안정 배포 후 `2.2.0-SNAPSHOT` 개발 train에서 9개 consumer의
Settings/CI를 immutable catalog commit `c44ec6c…`로 맞췄지만,
`post-publish-next-development-line` manifest는 이전 SHA `7a5995f…`를 유지했다.
초기 확인은 consumer 파일만 대조해 manifest 입력까지 같은 invariant로 확인하지
않았다. 이 불일치는 verifier가 새 ref를 거부하거나 snapshot 후보 branch를 이전
catalog에서 파생하게 만들 수 있었다.

## 결정

`snapshot-catalog-ref`는 consumer Settings/CI와 같은 release-train 입력으로
취급한다. manifest 값, signed tag의 peeled commit, 각 consumer의 Settings/CI ref가
모두 같은 immutable SHA를 가리켜야 한다. 별도 override는 실제로 다른 catalog를
사용해야 하는 consumer가 있는 경우에만 근거와 함께 둔다.

## 결과

P1을 child snapshot 재게시 전에 발견했다. 중앙 manifest와 회귀 테스트를 새 공통
SHA로 맞췄고, 이전 catalog train의 공개 snapshot은 이번 train의 검증 증거로
재사용하지 않도록 기록했다.

## 검증

- 개발선 verifier와 stable boundary의 집중 Python 테스트 32개 통과.
- `catalog/2026-11-24-01` 원격 tag object와 peeled commit 확인.
- 9개 consumer 후보의 Settings/CI SHA가 모두 동일함을 확인.
- 새 manifest 수정이 포함된 exact-head CI와 publication-POM gate, snapshot 재게시,
  public artifact read-back은 이 lesson 작성 시점에 pending이다.

## 향후 지침

새 catalog train을 고정할 때 consumer Settings/CI뿐 아니라 중앙 post-publish
manifest, candidate branch derivation, signed tag의 peeled commit을 한 번에 비교한다.
이 비교를 회귀 테스트로 유지하고, 이전 ref의 snapshot artifact는 같은 artifact
좌표를 사용하더라도 새 catalog train의 게시 증거로 계산하지 않는다.

다음 snapshot train에서는 먼저 최종 immutable catalog를 한 번 생성하고 모든
consumer와 verifier policy가 같은 commit SHA를 쓰게 한다. 이전 train처럼 consumer를
점진적으로 다른 catalog SHA에 옮기지 않는다. 사용자가 지적한 release 순서도 그대로
따른다: 공개 stable 기준은 Dependencies `2.1.0`으로 유지하고, 게시 child BOM의
의존 DAG를 따라 각 저장소의 Full Nightly와 자동 Publish Snapshot을 차례대로 완료한
뒤 metadata/POM/GMM HTTP 200을 확인한다. 선행 게시가 실패하면 후속 저장소로 건너뛰지
않고 그 지점부터 복구하며, 중앙 Dependencies snapshot은 여덟 child snapshot이 모두
공개된 다음에만 게시한다. 시작 전에 기존 release checklist와 GNO 이력을 다시 읽어
실행 순서와 각 단계의 성공 증거를 고정한다.
