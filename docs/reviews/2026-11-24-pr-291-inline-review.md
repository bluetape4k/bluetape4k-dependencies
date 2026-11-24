# PR #291 인라인 코드 리뷰

## 범위와 근거

- 저장소: `bluetape4k-dependencies`; PR #291, base `develop`.
- 검토한 source head: `08cdb92297a1494662ef2918dfe02f79409089c6`.
- 검토 범위: 다음 개발선 BOM/catalog, `post-publish-next-development-line`
  manifest와 verifier, 관련 회귀 테스트, 한·영 README 및 release 문서.
- 최신 정식 기준은 Dependencies/Projects/Exposed `2.1.0`, 나머지 child BOM
  `1.1.0`이다. 후보는 Dependencies/Projects/Exposed `2.2.0-SNAPSHOT`, 나머지
  child BOM `1.2.0-SNAPSHOT`이다.
- 공통 immutable catalog ref는 `catalog/2026-11-24-01`의 commit
  `c44ec6c47aa3a8dc3e862dbd7d041eb9d78355f3`; signed annotated tag object는
  `4d1351b5f65b773e9ed657694d063037061d42f4`다.
- 이번 문서 보정은 source 검토 결과를 갱신하고 downstream snapshot evidence를
  기록한다. 문서 보정 commit 뒤에는 exact-head CI, publication-POM contract,
  live review/thread 및 mergeability를 다시 확인한다.

## 이전 발견 사항의 처리

### P1 — verifier manifest와 consumer catalog ref 불일치: 해결

- 이전 `config/post-publish-next-development-line.json`은 consumer들이 고정한
  `c44ec6c47aa3a8dc3e862dbd7d041eb9d78355f3` 대신 이전 ref
  `7a5995fd46031ce1faf16337fa08d954436f8f9a`를 지정했다.
- manifest와 회귀 테스트의 기대값을 공통 SHA로 맞췄다. 아홉 consumer의
  Settings/CI read-back도 모두 같은 SHA를 사용한다.
- consumer가 다른 catalog에서 파생되거나 verifier가 유효한 후보를 거부할 수
  있던 원인을 제거했다.

### P1 — README가 미게시 stable Dependencies 버전을 안내: 해결

- 한·영 README의 central dependency 예시는 `2.2.0` stable 대신 다음 개발선인
  `2.2.0-SNAPSHOT`을 사용한다.
- 안정 consumer는 공식 Dependencies `2.1.0`을 사용하며 `2.2.0` stable은 아직
  이 train의 게시 대상이 아니다. 한·영 alias와 catalog/manifest 경계가 서로 맞는다.

## 현재 diff 검토

- `baseVersion=2.2.0`, 빈 `snapshotVersion=`, catalog self alias
  `2.2.0-SNAPSHOT`은 다음 개발선의 Gradle publication 계약과 일치한다.
- verifier는 manifest의 개발선 버전과 suffix로 self alias를 계산하고 snapshot
  suffix를 요구한다. stable 경계에서는 snapshot alias를 거부하는 회귀 조건이 있다.
- Projects, AWS, Experimental, Exposed, Graph, Image, JaVers, Leader, Text의
  Settings/CI pin은 모두 단일 catalog commit이다. Projects signed tag와 tag-object
  검증도 같은 catalog를 가리킨다.
- 중앙 Dependencies는 child BOM을 `api(platform(...))`로 가져온다. 게시 순서는
  Projects → Exposed → AWS → Graph → Image → JaVers → Leader → Text → Dependencies다.
  따라서 중앙 snapshot은 모든 child artifact 공개 뒤에 게시해야 한다.
- 검토한 source diff에서 해결되지 않은 P0/P1은 없다. public Kotlin/Java API나
  publisher workflow는 바꾸지 않는다.

## 검증 결과

- PR exact source head `08cdb92297a1494662ef2918dfe02f79409089c6`의 hosted CI run
  `45380017787`: 9개 PR checks PASS. Build BOM 및 Cross-repository Publication POM
  Contract도 PASS했다. Dependabot `submit-gradle` check도 PASS했다.
- 해당 시점 live PR은 OPEN, base `develop`, merge state `CLEAN`이었다.
  Review submissions, review threads/comments, issue comments는 모두 0개였다.
- 전체 publisher POM/effective-model gate는 이 run에서 통과했으나, 이번 문서 갱신을
  포함하는 새 PR head에서도 같은 contract를 재확인한다.
- 독립 reviewer lane은 `/opt/homebrew/Caskroom/codex/0.170.0/bin/codex-code-mode-host`
  실행 파일 부재로 verdict를 내지 못했다. 이 기록은 main-session inline fallback이며
  독립 리뷰 attestation이 아니다.

## 판정과 남은 hold

**인라인 source review: PASS — 미해결 P0/P1 없음.** 이전 두 P1은 수정된 source와
회귀 조건에서 해결됐음을 확인했다. 이 판정은 독립 reviewer attestation이 아니다.
사용자는 2026-11-24 단독 개발자 lane에서 독립 리뷰를 명시적으로 면제했고, 인간 리뷰
subgate는 `N/A (single-developer lane)`다. 인라인 source review는 계속 적용한다.

병합 전 문서 갱신 후 새 exact-head CI/POM contract와 live review/thread/mergeability를
다시 확인한다.
child publisher snapshot은 모두 공개됐지만 중앙 Dependencies snapshot, 그 뒤의
Experimental Dependency Submission 재실행과 최종 artifact/verifier read-back은 아직
완료하지 않았다.

## 2026-11-24 사용자 면제 결정 및 문서 변경 검토

- 사용자는 이 저장소가 단독 개발자 프로젝트이므로 독립 리뷰를 생략하라고 명시했다.
  저장소의 maintainer 범위는 `debop` 1인이므로 인간 리뷰 subgate는
  `N/A (single-developer lane)`다.
- 독립 reviewer attestation은 없다. 기존 판정은 main-session 인라인 source review이며,
  이번 변경도 이 구분을 유지한다. 사용자 면제는 인라인 검토, exact-head CI,
  review/thread read-back 또는 mergeability 확인을 면제하지 않는다.
- 이번 PR 문서 변경은 release checklist의 면제·게이트 상태와 이 review의 판정을
  명확히 한다. production source, catalog, verifier, tests, publication workflow는
  바꾸지 않는다. 이 문서 diff에서 해결되지 않은 P0/P1은 없다.
- 앞선 head `327b9a59cda5d4e561a6d2f0f1a07105c1ec84d5`의 9개 checks,
  publication-POM contract와 별도 `submit-gradle` run은 PASS했다. 이후 `WIP.md`만
  변경한 head `4b56d6534a32586c540f9e0f14c0814b5fa7c8f7`의 run `45400006863`은
  Build BOM과 publication-POM contract가 진행 중이다. 이 문서 갱신 후의 새 head에서
  exact-head proof를 다시 수집한다.

**판정: 인라인 source review PASS; 독립 리뷰는 사용자 지시에 따라 N/A.** 이 기록은
독립 reviewer attestation을 주장하지 않는다. 남은 병합 조건은 새 문서 head의 CI/POM,
최종 live review/thread/mergeability read-back이다. 중앙 snapshot, artifact read-back,
Experimental Dependency Submission 재시도는 병합 뒤 순서대로 진행한다.

## 문서 작성 검증

- 독자와 목적: 중앙 BOM maintainer를 위한 한국어 release-gate 코드 리뷰.
- 기술 사실의 기준: live PR/CI, source diff, immutable catalog tag, consumer refs,
  publisher snapshot metadata와 POM/GMM/JAR read-back.
- 인라인 검토와 독립 리뷰 결과를 구분했으며, 남은 hold를 완료된 검증처럼 표현하지 않았다.
- 최종 문서 저장 뒤 SPW/KO checklist와 contextual terminology audit 결과를 release
  checklist에 기록한다.
