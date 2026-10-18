# PR 본문 갱신 전 Type P 기준 정보 재확인

## 맥락

Issue [#1832](https://github.com/bluetape4k/bluetape4k-projects/issues/1832)의 catalog train에서 Dependencies PR [#267](https://github.com/bluetape4k/bluetape4k-dependencies/pull/267) 본문은 이전 head `9ac4173`과 해당 CI run을 현재 검증처럼 표시하고 있었다. 새 head `0803dbf04ce2272a9151cfac769937a39a211dc6`의 CI가 끝난 뒤 본문을 갱신하려 했지만, 첫 점검은 `bluetape-publish-jvm`의 필요한 항목을 검색한 데 그쳤다. PR을 수정하기 전에 선택한 leaf skill 전체와 발동된 reference를 다시 읽으라는 `CG-12A`를 완전히 충족하지 못한 절차상 실수였다.

## 결정 및 발견

PR 본문을 수정할 때도 현재 `AGENTS.md` 계층, 선택한 leaf skill, 공통 게이트, PR 템플릿, 연결 이슈를 갱신 직전에 다시 확인한다. 제목 검색이나 부분 발췌는 전체 문서 재확인을 대신하지 않는다. catalog train 본문에는 과거 head의 검증 기록과 최신 exact-head CI를 구분해 적고, `## DoD Status`에는 아직 승인이나 후속 소비자 작업이 필요한 상태를 남긴다.

## 결과

누락을 확인한 뒤 Type P skill과 catalog topology 및 publication-POM reference를 읽었다. head `0803dbf04ce2272a9151cfac769937a39a211dc6`의 CI run `39148769530`과 연결된 `submit-gradle` run `39148766154`가 모두 성공해 7/7 checks를 확인했고, 그 근거와 새 head를 PR 본문에 반영했다. GitHub read-back은 작성본과 같은 내용을 반환했고 마지막 줄바꿈 하나를 덧붙였다. PR은 여전히 OPEN/MERGEABLE이고 Issue #1832는 OPEN이다. 병합, immutable catalog ref, Projects pin, Dependency Submission, 실제 alert 재시도는 수행하지 않았다.

## 검증

- [Dependencies CI run 39148769530](https://github.com/bluetape4k/bluetape4k-dependencies/actions/runs/39148769530): exact head `0803dbf04ce2272a9151cfac769937a39a211dc6`, 6개 workflow checks 성공.
- 연결된 `submit-gradle` run `39148766154`: 성공. PR 전체 `gh pr checks` 결과는 7/7 pass.
- PR #267 live read-back: OPEN, MERGEABLE, head 일치, assignee `debop`, labels `ci`/`security`, milestone `2.1.0`; formal reviews, comments, review threads 없음.
- PR 본문은 8개 section heading을 원래 순서대로 유지하고 `## DoD Status`로 끝난다. Issue #1832는 계속 OPEN이다.

## 재발 방지

다음 PR 갱신 전 `CG-12A` 항목 전체를 확인하고, 현재 PR head·base·linked issue·required checks를 다시 읽는다. 갱신 뒤에는 live body를 다시 가져와 작성본과 마지막 줄바꿈 정규화를 제외하고 비교하고, section 순서와 마지막 DoD heading을 검사한다. head가 달라지면 이전 CI나 review verdict를 새 head의 근거로 재사용하지 않는다.
