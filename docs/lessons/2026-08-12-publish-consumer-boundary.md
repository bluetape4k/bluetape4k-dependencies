# Publish 후 소비자 경계는 저장소 역할로 나눈다

## 결론

다음 개발선을 열 때 내부 라이브러리와 예제 소비자를 같은 downstream으로
취급하면 안 된다.

- 내부 라이브러리는 게시되지 않은 모듈을 함께 개발하므로 immutable snapshot
  catalog commit과 `-SNAPSHOT` 내부 BOM ref를 사용한다.
- workshop/example/application은 사용자와 같은 소비자이므로 공식 배포된
  `bluetape4k-dependencies` BOM을 사용한다.
- JDK toolchain 전환은 dependency 소비 정책을 바꾸는 근거가 아니다.

## 실패 원인

기존 manifest의 `excluded-repositories`가 catalog-only 내부 저장소와
workshop/example/application을 한 범주로 묶었다. verifier도 게시자 8개만
검사해 예제가 snapshot BOM을 참조해도 실패하지 않았다. 그 결과 publish
skill의 `direct unreleased consumers` 경계를 실제 저장소 역할로 해석하지
못했다.

## 재발 방지

`consumer-policy`는 내부 snapshot catalog 저장소와 공식 배포 BOM 저장소를
서로 겹치지 않는 목록으로 관리한다. verifier는 내부 저장소의 exact catalog
SHA와 예제 저장소의 공식 BOM 버전을 함께 검사한다. CI와 snapshot publish
preflight는 두 목록에 필요한 저장소를 모두 checkout한 뒤 같은 검사를
실행한다.
