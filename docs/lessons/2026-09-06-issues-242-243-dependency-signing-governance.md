# dependency graph와 signing governance 검증 교훈

## 배경

Issues #242와 #243은 Timefold 후보 승격과 여러 publisher의 signing helper 통합을
한 validation train에서 다뤘다. 초기 graph runner는 Gradle 명령의 성공 여부만 검사했고,
signing 영수증은 기록된 digest가 실제 canonical source와 같은지 충분히 증명하지 못했다.

## 결정 또는 발견

- `dependencyInsight`의 exit code는 dependency 선택 증거가 아니다. 실제 좌표가 없을 때도
  명령이 성공할 수 있으므로 선택된 정확한 버전, `Selection reasons`, configuration과
  output digest를 함께 검증해야 한다.
- baseline과 candidate는 같은 immutable consumer HEAD에서 독립적으로 재현돼야 한다.
  이미 candidate로 변경된 worktree의 결과를 baseline으로 재사용할 수 없다.
- 영수증 내부 digest끼리의 일치는 provenance가 아니다. canonical source를 다시 해시해
  모든 repository와 consumer record가 그 값과 같은지 검증해야 한다.
- phase timeout만으로 전체 실행 budget을 보장할 수 없다. cache 조회와 job 제출 전에도
  하나의 전역 deadline과 누적 elapsed/remaining budget을 적용해야 한다.
- 중앙 governance script의 repository 목록은 공통 inventory에서 재사용해야 새 publisher가
  runner, sync, receipt validator 중 한 곳에서 누락되는 drift를 막을 수 있다.
- 여러 publisher에 helper를 쓰는 동안 canonical source나 repository map이 바뀌면 이미 쓴
  target까지 CAS rollback해야 한다. write 직전 확인만으로는 transaction 완료 시점의 입력을
  증명할 수 없다.

## 결과

semantic graph runner는 실제 소비 module만 조회하고 누락 좌표, 잘못된 선택 버전,
selection reason 부재를 fail-closed 처리한다. 그 결과 기존 `12/12 pass`를 무효화했고,
Exposed가 후보에서도 Timefold core `2.4.0`을 선택하는 사실과 독립 baseline 부재를
드러냈다. 중앙 catalog는 `2.4.0`을 유지했다.

signing governance는 9개 publisher가 같은 generated helper를 사용하고, local receipt가
실제 canonical source digest, 전체 validation budget, candidate Maven repository 전체
manifest를 검증하도록 강화됐다.

## 검증

Python 회귀 suite, 중앙 Gradle build, 9개 signing buildSrc smoke, 9개 repository의
publication POM/effective model, actionlint와 gitleaks를 실행했다. Timefold baseline과
candidate graph phase는 의도적으로 실패 상태를 유지하며, 통과로 승격하지 않았다.

## 향후 지침

dependency promotion은 “명령 성공”이나 일부 consumer 성공으로 완료 처리하지 않는다.
동일한 immutable baseline/candidate, 실제 resolved version과 selection reason, 필수 소비자
테스트가 모두 있어야 한다. provenance receipt는 기록된 값의 상호 일치가 아니라 실제
source·artifact·repository 상태와의 재계산으로 검증한다.
