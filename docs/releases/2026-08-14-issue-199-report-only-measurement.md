# Issue #199 report-only 공급망 증거 두 release train 측정

상태: **측정 완료 / report-only 유지 / 재생성 운영 공백은 후속 이슈 #206**

상위 이슈: [#163](https://github.com/bluetape4k/bluetape4k-dependencies/issues/163)

측정 이슈: [#199](https://github.com/bluetape4k/bluetape4k-dependencies/issues/199)

후속 이슈: [#206](https://github.com/bluetape4k/bluetape4k-dependencies/issues/206)

## 측정 경계

`Publish Snapshot` workflow가 성공한 두 실제 train의 동일한 report 경로를
immutable commit에서 읽어 비교했다. report의 finding은 release를 차단하지 않고,
malformed contract만 검증 실패로 해석한다. 두 train은 `develop`의
`e3c5f67b503e1fbeb50ce5e67dcb0f3ba40bc8dd`와
`0a500d4bb0995fdb1eb40ae4a4adec397fa611da`다.

## Train별 read-back

| Train | 성공한 snapshot 증거 | Report 경로 | 생성 시각 | 실행 명령 | Owner/evidence | Report SHA-256 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | [Publish Snapshot #31760338643](https://github.com/bluetape4k/bluetape4k-dependencies/actions/runs/31760338643), commit `e3c5f67b503e1fbeb50ce5e67dcb0f3ba40bc8dd` | [`config/supply-chain-report-only.json`](https://github.com/bluetape4k/bluetape4k-dependencies/blob/e3c5f67b503e1fbeb50ce5e67dcb0f3ba40bc8dd/config/supply-chain-report-only.json) | `2026-08-14T00:00:00+09:00` | `python3 scripts/verify-supply-chain-reports.py --summary` | report의 각 record `owner` 및 `evidence-url` | `468cd70c1e50a2c6f889a48f293a37449ed6a699fd036de6b1c588365a529008` |
| 2 | [Publish Snapshot #31802325407](https://github.com/bluetape4k/bluetape4k-dependencies/actions/runs/31802325407), commit `0a500d4bb0995fdb1eb40ae4a4adec397fa611da` | [`config/supply-chain-report-only.json`](https://github.com/bluetape4k/bluetape4k-dependencies/blob/0a500d4bb0995fdb1eb40ae4a4adec397fa611da/config/supply-chain-report-only.json) | `2026-08-14T00:00:00+09:00` | `python3 scripts/verify-supply-chain-reports.py --summary` | report의 각 record `owner` 및 `evidence-url` | `468cd70c1e50a2c6f889a48f293a37449ed6a699fd036de6b1c588365a529008` |

두 immutable report의 SHA-256과 `generated-at`이 동일하므로 두 번째 train에서
새 report를 생성하지 않고 첫 번째 snapshot을 재사용한 사실도 측정 결과로
기록한다. 다섯 owner(`dependency-governance`, `release-pipeline`,
`bluetape-go-maintainers`, `bluetape-py-maintainers`, `bluetape-rs-maintainers`)와
각 evidence URL은 두 blob에서 같은 JSON 필드로 read-back된다.

## 검증 결과 비교

| 지표 | Train 1 | Train 2 | 판정 |
| --- | ---: | ---: | --- |
| 전체 record | 7 | 7 | schema 범위 동일 |
| `pass` | 2 | 2 | 변화 없음 |
| `review` | 2 | 2 | low severity inventory 관찰 2건 유지 |
| `not-applicable` | 3 | 3 | 언어별 scanner는 각 저장소 소유 |
| `high`/`critical` + reachable | 0 | 0 | triage 후보 없음 |
| 만료 exception | 0 | 0 | 별도 대응 없음 |
| exception 갱신 | 0 | 0 | 갱신 이벤트 없음 |
| triage 소요 | 0분 | 0분 | blocking 후보가 없어 즉시 no-op 분류; 실제 사람 대응 시간은 미발생 |

현재 bytes에서 같은 명령을 다시 실행한 검증기 runtime은 `real 0.06s`였다.
이 수치는 과거 train의 wall-clock 운영 시간을 소급한 값이 아니며, 구조 검증
실행 비용의 참고치로만 보존한다.

```text
Supply-chain report-only: records=7; not-applicable=3, pass=2, review=2; blocking-candidates=0; expired-exceptions=0; findings do not fail this gate
```

## 비교 결론과 다음 단계

1. 두 train 모두 `review=2`, severe reachable candidate=0, expired exception=0으로
   noise와 즉시 대응량은 낮았다.
2. 그러나 `generated-at`과 SHA-256이 변하지 않아 train별 report 재생성 및
   실제 운영 대응 시간은 검증되지 않았다. 이는 결과를 실패로 만들지 않지만,
   측정 완결성의 공백이다.
3. 따라서 현재는 **report-only를 유지**한다. evidence 갱신과 owner 안정성,
   severe/expired 처리 절차가 실제로 검증되기 전에는 release-blocking failure
   gate로 승격하지 않는다.
4. train별 재생성과 triage 시각을 다음 snapshot에서 기록하는 작업은
   [#206](https://github.com/bluetape4k/bluetape4k-dependencies/issues/206)에
   등록했다. gate 승격이나 SBOM/attestation 제품화는 별도 이슈와 새 승인으로
   남긴다.

## 범위 밖

- Gradle/Go/Python/Rust dependency version 일괄 변경
- Dependabot alert 종료
- release-blocking gate, 자동 exception 만료, SBOM/attestation 제품화
- tag, Maven Central publication, GitHub Release, merge 및 cleanup
