# Dependabot 변경과 generated artifact CI drift

## 배경

Dependabot PR #220은 `gradle/libs.versions.toml`의 Kotlin benchmark 버전을 갱신했고,
PR #221은 CI workflow의 `actions/setup-java` major version을 올렸다. 두 PR 모두 각
변경의 원본 파일만 수정한 채 병합되어 `develop`의 `Build BOM` 검증이 실패했다.

## 원인

- catalog 변경 뒤 `libs.versions.toml.sha256`, latest-stable inventory, audit를 함께
  재생성하지 않아 provenance chain이 이전 catalog를 가리켰다.
- workflow가 `actions/setup-java@v6.0.0`을 사용하지만 CI policy test는 여전히
  `actions/setup-java@v5`를 요구했다.
- aggregate `CI Status` 실패는 별도 결함이 아니라 위 `Build BOM` 실패의 결과였다.

## 결정

catalog source가 바뀌면 checksum과 inventory를 같은 변경에서 재생성하고 audit의
catalog/inventory 연결과 영향받은 current line을 함께 재기준화한다. historical audit의
전체 metadata refresh는 별도 report regeneration 범위이므로 이 복구에 섞지 않는다.
GitHub Action version을 올릴 때는 workflow와 policy test가 같은 major line을 검증하도록
함께 갱신한다. exact patch version 대신 major line을 검사해 Dependabot의 patch update를
허용한다.

## 검증

수정 전에는 checksum, inventory, `setup-java` policy test가 각각 실패했다. 수정 후 동일한
세 테스트가 통과했고, Python test는 `301`개를 실행해 `299`개가 통과했다. Maven
`-SNAPSHOT` artifact 조회에서 HTTP `403`을 받은 `2`개는 명시적으로 skip됐다. catalog audit는 authority `515`,
line `549`, current `449`, `adopt-latest` 후보 `0`을 유지했다. managed artifact `183`개
검증과 Gradle build도 통과했다.

2026-10-21 중앙 PR #270에서도 같은 누락이 재발했다. 초기 exact-head CI
[39601336675](https://github.com/bluetape4k/bluetape4k-dependencies/actions/runs/39601336675)의
Python 검증은 `515` tests 중 failures `16`, errors `1`, skipped `4`를 보고했다.
후보 catalog SHA가 `11255a5e195a2e66574559fff4568e4551f5b58ab89c68fabeffa2197e331f30`으로
바뀌었지만 inventory와 audit는 이전 catalog/inventory SHA를 계속 참조했다. 변경 대상인
Bouncy Castle record에는 이미 `2.73.13` metadata와 `2026-10-18T09:35:19Z` 조회 시각이
있었다. inventory를 재생성하고 해당 current line과 disposition, 입력 SHA, summary만
갱신했다. `config/latest-stable-version-deltas.json`의 현재 audit SHA와 summary도 새 audit에
맞췄다. metadata 조회 시각과 나머지 record는 유지했다. audit check와
`tests.test_audit_latest_stable`의 `38` tests는 통과했지만, 전체 Python suite는
`test_rollout_audit_summary_matches_its_lifecycle` 한 건에서 실패했다. 그 테스트는
`latest-stable-version-deltas.json`이 현재 audit의 SHA/summary를 보관하는 계약을 검증했다.
audit pointer를 현재 파일에 맞추자 기존 resolved-graph receipt의 ledger-contract SHA와
후보 검증 receipt에 저장된 graph receipt SHA도 갱신해야 했다. graph 관찰은 바뀌지 않았지만
receipt contract SHA가 바뀌어 candidate receipt의 nested graph SHA와 latest-stable/central
ledger의 graph receipt SHA pointer를 함께 갱신했다. audit/delta 모듈 `48` tests와 central
ledger SHA 검사 `7` tests가 통과했다. 전체 Python suite `516` tests도 통과했고,
`-SNAPSHOT` artifact 조회에서 HTTP `403`을 받은 항목은 verifier가 별도로 건너뛰었다.
suite 자체의 `skipped=2`는 managed sibling
repositories를 찾지 못한 workspace-wide 검증 두 건이며, 새 PR head의 hosted CI 결과는 아직
대기 중이었다. 이후 PR head `3c7a47bf335fbc543f7dbc1f33f9bf5f5134bedd`의 CI run
[39627022926](https://github.com/bluetape4k/bluetape4k-dependencies/actions/runs/39627022926)은
9개 job이 통과했다. 다만 PR 이벤트에서는 downstream consumer 동기화가 조건상 실행되지 않아
아홉 저장소의 catalog SHA 일치는 증명하지 못했다. 이 실패를 고치며 중앙 policy의 Projects
override를 현재 consumer pin에 맞췄지만, 기본 ref와 override가 다른 전환 상태가 남았다.
2026-10-22 live `develop` read-back에서 Projects settings/CI는
`dcc7fa7557d3c0548b9e3fc28c48877827ea2f74`를 사용하고 기존 tag
`catalog/2026-10-20-01`도 그 commit을 가리킨다. AWS, Experimental, Exposed, Graph, Image,
JaVers, Leader, Text의 settings/CI는 `198147fd6ca2992fae32e175bd5f3d396c497096`를 사용한다.
따라서 저장소 내부 pin 일치와 아홉 저장소 간 단일 SHA 수렴은 별도 조건이다.

audit 요약 pointer는 갱신했지만 resolved dependency graph는 바뀌지 않아
`central-catalog-version-deltas.json`에 새 delta를 추가하지 않았다.

## 재발 방지

catalog 변경은 원본, checksum, latest-stable inventory와 audit를 한 번에 맞춘다.
`python3 scripts/audit-latest-stable.py --write --summary`로 inventory를 재생성한 뒤,
버전이 달라진 authority의 audit line과 입력 SHA 및 summary를 현재 inventory에 맞춘다.
기존 upstream metadata가 유효하면 해당 record만 재기준화하고 조회 시각과 나머지 record를
보존한다. 전체 `--refresh-audit`는 별도의 report regeneration 범위가 승인된 경우에만
사용한다. audit를 변경했다면 `latest-stable-version-deltas.json`의 audit SHA/summary pointer도
현재 audit를 가리키는지 확인한다. audit pointer 변경으로 resolved-graph contract가 달라지면
receipt를 재검증하고 candidate receipt의 nested SHA 및 `latest-stable-version-deltas.json`,
`central-catalog-version-deltas.json`의 graph receipt SHA pointer를 함께 맞춘다. push 전에는
`python3 scripts/audit-latest-stable.py --check --summary --check-audit --audit-summary`와
`python3 -m unittest tests.test_audit_latest_stable tests.test_latest_stable_version_deltas`를
실행한다. 두 ledger가 기록한 receipt SHA와 실제 파일 digest가 일치하는지도 검사한다.
`central-catalog-version-deltas.json`에는 실제 resolved graph가 달라진 경우에만 delta를
추가한다. 검증이 빠진 PR은 후속 PR에 섞지 않고 prerequisite fix로 먼저 복구한다.

여러 consumer가 중앙 catalog를 사용할 때 policy override로 개별 ref drift를 맞추는 작업은
전환 상태로 기록한다. 단일 SHA 수렴이 요구되면 중앙 catalog train의 tag가 확정된 뒤 각
consumer의 `settings.gradle.kts`와 CI pin을 같은 40자리 commit SHA로 갱신한다. 모든 consumer가
그 SHA로 수렴한 다음 중앙 `snapshot-catalog-ref`도 같은 값으로 바꾸고
`snapshot-catalog-ref-overrides`를 비운다. 마지막으로 consumer policy verifier를 다시 실행해
모든 저장소와 중앙 policy가 같은 ref를 사용함을 확인한다. PR 이벤트에서 downstream sync job이
skip되면 CI 녹색만으로 이 조건을 통과 처리하지 않는다.
