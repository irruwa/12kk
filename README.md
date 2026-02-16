# YouTube 영어 스크립트 학습기

유튜브 자막(스크립트) 텍스트를 넣으면 다음을 자동으로 만들어주는 파이썬 프로그램입니다.

- 자주 나오는 핵심 단어 목록
- 단어가 포함된 예문
- 빈칸 채우기(filling blank) 문제
- (옵션) 콘솔 퀴즈
- (신규) 웹 브라우저에서 바로 확인 가능한 UI

## 실행 방법

### 1) 콘솔 실행

```bash
python youtube_english_study.py --input transcript.txt
```

### 2) 웹 실행 (브라우저에서 직접 보기)

```bash
python youtube_english_study.py --web
```

실행 후 브라우저에서 `http://127.0.0.1:8000` 접속해서 스크립트를 붙여넣고 분석할 수 있습니다.

## 옵션 예시

```bash
# 상위 30개 단어 추출
python youtube_english_study.py --input transcript.txt --top 30

# JSON 파일로 저장
python youtube_english_study.py --input transcript.txt --json-out study_pack.json

# 퀴즈 모드
python youtube_english_study.py --input transcript.txt --quiz

# 파이프 입력
cat transcript.txt | python youtube_english_study.py --stdin

# 웹 포트/호스트 지정
python youtube_english_study.py --web --host 0.0.0.0 --port 9000
```

## 입력 파일

- 일반 텍스트(.txt)
- 자막 파일(.srt/.vtt 형태의 텍스트)

프로그램이 숫자 인덱스, 타임스탬프, `-->` 같은 자막 표식을 최대한 제거한 뒤 학습용 데이터로 변환합니다.
