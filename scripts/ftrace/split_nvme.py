import argparse
import re
import os

## INFO: Qdepth 수정해야함

io_dict = {} # cmd_id, IO
queue = {} # qid, qdepth
qdepth_int = 0

class IO:
    qid: int
    qdepth : int
    qdepth_total : int
    cmd_id: int
    cmd_type: str
    issue_time: float
    comp_time: float
    slba: int
    len: int
    dsmgmt: int
    latency: float #us

    def __init__(self, qid, cmd_id, cmd_type, issue_time, slba_value, len_value, dsmgmt_value):
        self.qid = qid

        if self.qid not in queue:
            queue[self.qid] = 0
        queue[self.qid] = queue[self.qid] + 1 # Qdepth 증가

        global qdepth_int
        qdepth_int = qdepth_int + 1

        self.qdepth = queue[self.qid] # issue 시점의 Qdpeth
        self.qdepth_total = sum(queue.values())
        self.cmd_id = cmd_id
        self.cmd_type = cmd_type
        self.issue_time = issue_time
        self.slba = slba_value
        self.len = len_value
        self.dsmgmt = dsmgmt_value

    def completed(self, comp_time):
        queue[self.qid] = queue[self.qid] - 1 # Qdepth 감소
        global qdepth_int
        qdepth_int = qdepth_int - 1
        #print(qdepth_int, sum(queue.values()))
        self.comp_time = comp_time
        self.latency = round((self.comp_time - self.issue_time) * 1000, 3)
    
    def toCsv(self):
        return f"{self.cmd_id},{self.cmd_type},{self.issue_time},{self.comp_time},{self.qid},{self.qdepth},{self.qdepth_total},{self.latency},{self.slba},{self.len},{self.dsmgmt}\n"

def parse_time(line):
    # line 샘플
    #  <idle>-0       [010] d.h1. 14263.518121: nvme_complete_rq: nvme0: disk=nvme0n1, qid=11, cmdid=33219, res=0x0, retries=0, flags=0x0, status=0x0

    # 정규식 패턴
    pattern = r"(\d+\.\d+):.*?"

    #정규식 검색
    match = re.search(pattern, line)

    timestamp = 0
    if match:
        timestamp = float(match.group(1))
    else:
        print(f'[ERROR] Can not parse timestamp \n{line}')

    return timestamp


def main(args):
    input_file = args.input_file
    filename = os.path.splitext(input_file)[0]

    with open(input_file, 'r') as file:
        file_cnt = 0
        output_filename = f'{filename}_S{file_cnt}.trace'
        output_file = open(output_filename, 'w', newline='')
        header = ""
        
        for i, line in enumerate(file):
            # if i < 1000000:
            cur_time = parse_time(line)

            if i == 0: # First line
                prev_time = cur_time

            if False: #(cur_time - prev_time) > 300: # if over 5min. then, change file
                output_file.close()
                file_cnt += 1
                output_filename = f'{filename}_S{file_cnt}.trace'
                output_file = open(output_filename, 'w', newline='')
                output_file.write(header)
                
            output_file.write(line)
            prev_time = cur_time
            
        output_file.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Description of your program")

    # 인수 추가
    parser.add_argument("-i", "--input_file", type=str, help="Input file path")

    # 명령행 인수 파싱
    args = parser.parse_args()

    # main 함수 호출
    main(args)

