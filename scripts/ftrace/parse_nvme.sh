#!/bin/bash

if [[ $# -ne 1 ]]; then
  echo "invalid parameters"
  echo "(ex) ./parse_nvme.h test.trace"
  exit 1
fi

DIR=$PWD"/"
FILENAME=$(echo $1 | cut -d '.' -f1)
#FILENAME=${FILENAME[0]}
echo $FILENAME
INPUT_FILE=$DIR$1


#DIR=/home/ihhwang/git/fdp/util
SPLIT_PY=${DIR}'/split_nvme.py'
PARSE_PY=${DIR}'/parse_nvme.py'
STATS_PY=${DIR}'/stats_nvme.py'


# Parsing
echo "[0] Split"
# find 명령어로 $DIR에서 $FILENAME으로 시작하는 파일 검색
found_files=$(find "$DIR" -type f -name "$FILENAME""_S*.trace" | sort)

# 파일이 존재하는지 확인
if [ -z "$found_files" ]; then
	echo " Cant' find the split file."
  echo  " Do Split" $INPUT_FILE
  python3 $SPLIT_PY -i $INPUT_FILE
else
  # 파일이 있는 경우 파일명 출력
	echo " Skip split file, already exist"
  echo "$found_files" | while IFS= read -r file; do
    echo "  File : $(basename "$file")"
  done
fi
echo "[0] Split Done"

found_files=$(find "$DIR" -type f -name "$FILENAME""_S*.trace" | sort)
for file in $found_files; do
  filesize=$(stat -c%s "$file")
    
  # 파일 크기가 1MB(1048576 바이트) 이하인 경우 무시
  if [ "$filesize" -le 1048576 ]; then
    echo "[X] Skip '$file' (<1MB)"
    continue
  fi

  FILENAME=$(echo $file | cut -d '.' -f1)

  echo "[-] RUN" $file
  TRACE_FILE=$FILENAME".trace"
  PARSE_FILE=$FILENAME".parse"
  STATS_FILE=$FILENAME".stats"
  echo "[1] Parse"
  if [[ -f $PARSE_FILE ]]; then
    echo "  Already exist the parsed file. Skip"
  else
    python3 $PARSE_PY -i $TRACE_FILE -o $PARSE_FILE
  fi

  echo "[2] Calculate"
  python3 $STATS_PY -i $PARSE_FILE -o $STATS_FILE
done


echo "[Completed]"

