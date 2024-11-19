import argparse
import re

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

def parse_complete_rq(line):
    # line 샘플
    #  <idle>-0       [010] d.h1. 14263.518121: nvme_complete_rq: nvme0: disk=nvme0n1, qid=11, cmdid=33219, res=0x0, retries=0, flags=0x0, status=0x0

    # 정규식 패턴
    pattern = r"(\d+\.\d+):.*?qid=(\d+).*?cmdid=(\d+)"

    #정규식 검색
    match = re.search(pattern, line)

    if match:
        timestamp = float(match.group(1))
        qid = int(match.group(2))
        cmd_id = int(match.group(3))
        key = f'{qid}_{cmd_id}'

        # io_dict에서IO[cmd_id]를 찾고 출력값 저장 및 IO 객체 삭제
        if key in io_dict:
            io_dict[key].completed(timestamp)
            ret = io_dict[key].toCsv()
            del io_dict[key]
            return ret

def parse_setup_cmd(line):
    # line 샘플
    # line='systemd-udevd-47096   [010] ..... 91444.019570: nvme_setup_cmd: nvme0: disk=nvme0n1, qid=11, cmdid=57664, nsid=1, flags=0x0, meta=0x0, cmd=(nvme_cmd_read slba=918149376, len=25, ctrl=0x8000, dsmgmt=7, reftag=0)'

    # 정규식 패턴
    pattern = r"(\d+\.\d+):.*?qid=(\d+).*?cmdid=(\d+).*?cmd=\((.*?) slba=(\d+).*?len=(\d+).*?dsmgmt=(\d+)"
   
    # 정규식 검색
    match = re.search(pattern, line)

    if match:
        timestamp = float(match.group(1))
        qid = int(match.group(2))
        cmd_id = int(match.group(3))
        cmd_value = match.group(4)
        slba_value = int(match.group(5))
        len_value = int(match.group(6))
        #dsmgmt_value = int(match.group(7))
        # 16bit shift 하여, pid 로 변환
        dsmgmt_value = int(match.group(7)) >> 16
        cmd_type = "NONE"
        if cmd_value == "nvme_cmd_read":
            cmd_type = "READ"
        elif cmd_value == "nvme_cmd_write":
            cmd_type = "WRITE"
        else:
            cmd_type = "ERR"


        key = f'{qid}_{cmd_id}'
        io_dict[key] = IO(qid, cmd_id, cmd_type, timestamp, slba_value, len_value, dsmgmt_value)
        return True
        # print(timestamp, cmd_type, slba_value, len_value, dsmgmt_value)
        # return f"{timestamp} {cmd_type} {slba_value} {len_value} {dsmgmt_value}\n"
        #print("Timestamp:", timestamp)
        #print("CMD 값:", cmd_value)
        #print("SLBA 값:", slba_value)
        #print("LEN 값:", len_value)
        #print("DSMGMT 값:", dsmgmt_value)
    else:
        print(line)
        return False

def main(args):
    input_file = args.input_file
    output_file = args.output_file

    with open(input_file, 'r') as file:
        with open(output_file, 'w') as output_file:
            output_file.write('cmd_id,cmd_type,issue_time,comp_time,qid,qdepth,qdepth_total,latency,slba,len,dsmgmt\n')
            for i, line in enumerate(file):
                # if i < 1000000:
                if i > -1:
                    if "nvme_setup_cmd" in line:
                        isPass = parse_setup_cmd(line)
                    elif "nvme_complete_rq" in line:
                        result = parse_complete_rq(line)
                        if result is not None:
                            output_file.write(result)
                else:
                    break
            

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Description of your program")

    # 인수 추가
    parser.add_argument("-i", "--input_file", type=str, help="Input file path")
    parser.add_argument("-o", "--output_file", type=str, help="Output file path")

    # 명령행 인수 파싱
    args = parser.parse_args()

    # main 함수 호출
    main(args)

