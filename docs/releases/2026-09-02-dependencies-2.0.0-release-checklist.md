# bluetape4k-dependencies 2.0.0 release checklist

## 고정 입력

- Target version: `io.github.bluetape4k:bluetape4k-dependencies:2.0.0`
- Latest observed external version: `io.github.bluetape4k:bluetape4k-bom:2.0.0`
- Projects release commit: `8165a8989e0075e7c17c489bf3000bf41fef8232`
- Publication authority: 이번 bluetape4k ecosystem 정식 배포와 후속 조치를
  완료하라는 사용자 승인
- Consumer scope: 9개 internal library/catalog consumer와 최종 stable BOM을
  사용하는 workshop/example/application consumer
- Dispatch hold: 모든 internal sub-BOM의 stable 공개, central catalog 승격,
  최종 downstream exact-commit handoff가 끝날 때까지 dependencies 2.0.0 tag,
  release workflow, Maven Central publication을 실행하지 않음

## 선행 release DAG

- [x] Projects 2.0.0 signed tag와 exact release commit 검증
- [x] Projects exact-head Full Nightly 47/47 성공
- [x] Projects Maven Central publication 및 대표 artifact HTTP 200
- [x] Projects GitHub Release와 2.0.0 milestone 종료
- [x] Central catalog에서 Projects BOM을 stable 2.0.0으로 승격
- [x] Post-publish guard가 Projects만 stable, 미배포 7개 BOM은 SNAPSHOT으로 검증
- [ ] Exposed 2.0.0, Graph/Image/Text 1.0.0 정식 공개
- [ ] Central catalog에서 Exposed BOM을 stable 2.0.0으로 승격
- [ ] AWS/Javers/Leader 1.0.0 정식 공개
- [ ] 모든 internal BOM을 stable로 승격한 최종 catalog commit 확정
- [ ] 모든 consumer를 최종 exact catalog commit으로 handoff

## Dependencies 2.0.0 publication gate

- [ ] `gradle/libs.versions.toml`에 SNAPSHOT internal BOM ref가 없음
- [ ] portable catalog checksum 일치
- [ ] managed catalog와 shared version sync 검증 통과
- [ ] 모든 managed repository publication POM 검증 통과
- [ ] `./gradlew build` 통과
- [ ] release target exact SHA의 required CI가 terminal success
- [ ] signed annotated tag가 exact release commit을 가리킴
- [ ] Maven Central publication과 공개 POM/module metadata HTTP 200
- [ ] GitHub Release 생성 및 2.0.0 milestone 종료

## DoD Status

- 상태: PENDING
- 현재 완료: Projects 2.0.0 공개 및 central catalog 승격 준비
- 남은 hold: 나머지 7개 internal BOM release와 최종 consumer handoff
