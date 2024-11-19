import argparse
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.colors import ListedColormap
from scipy.interpolate import make_interp_spline
from scipy.stats import gaussian_kde
from scipy.stats import zscore
import os

io_dict = {} # cmd_id, IO

class IO:
    cmd_id: int
    cmd_type: str
    issue_time: float
    comp_time: float
    slba: int
    len: int
    dsmgmt: int
    latency: float

    def __init__(self, cmd_id, cmd_type, issue_time, slba_value, len_value, dsmgmt_value):
        self.cmd_id = cmd_id
        self.cmd_type = cmd_type
        self.issue_time = issue_time
        self.slba = slba_value
        self.len = len_value
        self.dsmgmt = dsmgmt_value

    def completed(self, comp_time):
        self.comp_time = comp_time
        self.latency = round((self.comp_time - self.issue_time) * 1000, 3)
    
    def toCsv(self):
        return f"{self.cmd_id},{self.cmd_type},{self.issue_time},{self.comp_time},{self.latency},{self.slba},{self.len},{self.dsmgmt},\n"

def parse_complete_rq(line):
    # line 샘플
    #  <idle>-0       [010] d.h1. 14263.518121: nvme_complete_rq: nvme0: disk=nvme0n1, qid=11, cmdid=33219, res=0x0, retries=0, flags=0x0, status=0x0

    # 정규식 패턴
    pattern = r"(\d+\.\d+):.*?cmdid=(\d+)"

    #정규식 검색
    match = re.search(pattern, line)

    if match:
        timestamp = float(match.group(1))
        cmd_id = int(match.group(2))

        # io_dict에서IO[cmd_id]를 찾고 출력값 저장 및 IO 객체 삭제
        if cmd_id in io_dict:
            io_dict[cmd_id].completed(timestamp)
            ret = io_dict[cmd_id].toCsv()
            del io_dict[cmd_id]
            return ret

def parse_setup_cmd(line):
    # line 샘플
    # line='systemd-udevd-47096   [010] ..... 91444.019570: nvme_setup_cmd: nvme0: disk=nvme0n1, qid=11, cmdid=57664, nsid=1, flags=0x0, meta=0x0, cmd=(nvme_cmd_read slba=918149376, len=25, ctrl=0x8000, dsmgmt=7, reftag=0)'

    # 정규식 패턴
    pattern = r"(\d+\.\d+):.*?cmdid=(\d+).*?cmd=\((.*?) slba=(\d+).*?len=(\d+).*?dsmgmt=(\d+)"
   
    # 정규식 검색
    match = re.search(pattern, line)

    if match:
        timestamp = float(match.group(1))
        cmd_id = int(match.group(2))
        cmd_value = match.group(3)
        slba_value = int(match.group(4))
        len_value = int(match.group(5))
        dsmgmt_value = int(match.group(6))
        cmd_type = "NONE"
        if cmd_value == "nvme_cmd_read":
            cmd_type = "READ"
        elif cmd_value == "nvme_cmd_write":
            cmd_type = "WRITE"
        else:
            cmd_type = "ERR"


        io_dict[cmd_id] = IO(cmd_id, cmd_type, timestamp, slba_value, len_value, dsmgmt_value)
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

def draw_latencySimple(fig, axis, df, x_data):
    mean_latency = df['latency'].median()

    # 'latency'와 'issue_time' 열의 데이터 추출
    latency = df['latency']
    issue_time = df['issue_time']
    slba = df['slba']
    size = df['len']

    #norm_size = (size - size.min()) / (size.max() - size.min())


    # 첫 번째 플롯: Latency 산점도
    axis.set_title('Latency vs. Issue Time')
    axis.set_xlabel('Issue Time')
    axis.set_ylabel('Latency')

    Q1 = latency.quantile(0.01)
    Q3 = latency.quantile(0.99)
    IQR = Q3 - Q1

    # 1-1 Area chart (min-max)
    # Outlier를 제외한 데이터 필터링
    outlier_threshold_low = Q1 - 1.5 * IQR
    outlier_threshold_high = Q3 + 1.5 * IQR
    filtered_data = df[(latency >= outlier_threshold_low) & (latency <= outlier_threshold_high)]
    filtered_data = filtered_data.copy()  # 복사본 생성

    # issue_time을 100개로 분할하여 각 구간의 min/max 계산
    bins = np.linspace(issue_time.min(), issue_time.max(), 1001)  # 100개의 구간 경계 생성
    filtered_data['issue_time_binned'] = np.digitize(filtered_data['issue_time'], bins)  # issue_time을 구간에 따라 분할

    # 각 구간에서 latency의 min/max 계산
    latency_grouped = filtered_data.groupby('issue_time_binned')['latency'].agg(['min', 'max']).reset_index()
    
    # 각 구간의 중심값을 구해 x축으로 사용
    latency_grouped['issue_time_mid'] = latency_grouped['issue_time_binned'].apply(
        lambda x: (bins[x-1] + bins[x])/2 if x < len(bins)-1 else (bins[x-1] + bins[-1])/2
    )

    # min/max 값이 0인 구간을 필터링
    latency_grouped = latency_grouped[(latency_grouped['min'] > 0) & (latency_grouped['max'] > 0)]

    # Interpolation for min and max
    min_smooth = make_interp_spline(latency_grouped['issue_time_mid'], latency_grouped['min'], k=3)(latency_grouped['issue_time_mid'])
    max_smooth = make_interp_spline(latency_grouped['issue_time_mid'], latency_grouped['max'], k=3)(latency_grouped['issue_time_mid'])


    # Area plot으로 min-max 범위 표현
    #axis.fill_between(latency_grouped['issue_time_mid'], latency_grouped['min'], latency_grouped['max'], color='skyblue', alpha=0.4)
    axis.fill_between(latency_grouped['issue_time_mid'], min_smooth, max_smooth, color='skyblue', alpha=1.0)

    # 1-2 Contour
    # Data sampling - 10%
    sample_df = df.sample(frac=0.1, random_state=42)
    sample_latency = sample_df['latency']
    sample_issue_time = sample_df['issue_time']

    # Outlier 제외 (IQR 방법 사용)
    latency_no_outliers = sample_latency[(sample_latency >= (Q1 - 1.5 * IQR)) & (sample_latency <= (Q3 + 1.5 * IQR))]
    issue_time_no_outliers = sample_issue_time[sample_latency.index.isin(latency_no_outliers.index)]

    print(latency_no_outliers.max())
    # 데이터의 밀집도를 추정하기 위해 커널 밀도 추정 (KDE) 사용
    kde = gaussian_kde(np.vstack([issue_time_no_outliers, latency_no_outliers]))

    # 스무딩을 위한 메쉬 생성
    issue_time_range = np.linspace(issue_time_no_outliers.min(), issue_time_no_outliers.max(), 100)
    latency_range = np.linspace(latency_no_outliers.min(), latency_no_outliers.max(), 100)
    issue_time_mesh, latency_mesh = np.meshgrid(issue_time_range, latency_range)
    positions = np.vstack([issue_time_mesh.ravel(), latency_mesh.ravel()])
    density = kde(positions).reshape(issue_time_mesh.shape)

    # 사용자 정의 컬러맵 생성
    colors = [(1, 1, 1, 0), (1, 1, 1, 0), (0, 0, 1, 0.5), (1, 0, 0, 1)]  # RGBA: 투명, 파랑, 빨강
    positions = [0, 0.1, 0.5, 1]  # 컬러맵의 위치 (0: 노랑, 0.7: 파랑, 1: 빨강)
    n_bins = 100  # Number of bins
    cmap_name = 'custom_cmap'
    custom_cmap = LinearSegmentedColormap.from_list(cmap_name, list(zip(positions, colors)), N=n_bins)

    contour = axis.contourf(issue_time_mesh, latency_mesh, density, cmap=custom_cmap, alpha=0.7)

    # 1-2 Scatter
    # Outlier 만 사용
    latency_outliers = latency[latency > latency_no_outliers.max()]
    issue_time_outliers = issue_time[latency.index.isin(latency_outliers.index)]
    size_outliers = size[latency.index.isin(latency_outliers.index)]
    # 산점도 플로팅 (극단적인 outlier)
    sc = axis.scatter(issue_time_outliers, latency_outliers, c=size_outliers, cmap='coolwarm', edgecolor='none', alpha=0.7)


    #sc = axis.scatter(issue_time_outliers, latency_outliers, c=size_outliers, cmap='coolwarm', edgecolor='none', alpha=0.5)
    fig.colorbar(sc, ax=axis, label='Size(KB)')

    # 1-3 최대값과 최소값 수직선 추가
    #axis.axhline(latency.max(), color='red', linestyle='--', label=f'Latency Max: {latency.max():.3f}')
    #axis.axhline(latency.mean(), color='blue', linestyle='--', label=f'Latency Min: {latency.mean():.3f}')

def draw_column(fig, axis, df, column, title, ymax=0):
    # 'latency'와 'issue_time' 열의 데이터 추출
    y_data = df[column]
    issue_time = df['issue_time']
    size = df['len']

    sc = axis.scatter(issue_time, y_data, c=size, s=1, cmap='coolwarm', edgecolor='none', alpha=0.5)
#    sc = axis.scatter(issue_time, y_data, s=1, color='blue', edgecolor='none', alpha=0.5)
    axis.set_title(title)
    axis.set_xlabel('Issue Time')
    axis.set_ylabel(column)
    fig.colorbar(sc, ax=axis, label='Size(KB)')

    if ymax > 0 :
        axis.set_ylim(0, ymax)

def draw_column_pid(fig, axis, df, column, title, ymax=0):
    # 'latency'와 'issue_time' 열의 데이터 추출
    y_data = df[column]
    issue_time = df['issue_time']
    size = df['dsmgmt']
    listcmap = ListedColormap(['red', 'green', 'blue', 'purple', 'orange', 'black', 'yellow', 'cyan'])

    sc = axis.scatter(issue_time, y_data, c=size, cmap=listcmap, edgecolor='none', alpha=0.9)
    axis.set_title(title)
    axis.set_xlabel('Issue Time')
    axis.set_ylabel(column)
    fig.colorbar(sc, ax=axis, label='PID')

    if ymax > 0 :
        axis.set_ylim(0, ymax)


#Latency 산점도
def draw_latency(fig, axis, df, title):
    # 'latency'와 'issue_time' 열의 데이터 추출
    latency = df['latency']
    issue_time = df['issue_time']
    size = df['len']

    sc = axis.scatter(issue_time, latency, c=size, cmap='coolwarm', edgecolor='none', alpha=0.5)
    axis.set_title(title)
    axis.set_xlabel('Issue Time')
    axis.set_ylabel('Latency')
    fig.colorbar(sc, ax=axis, label='Size(KB)')

#LBA 산점도
def draw_lba(fig, axis, df, title):
    # 'latency'와 'issue_time' 열의 데이터 추출
    issue_time = df['issue_time']
    slba = df['slba']
    size = df['len']

    sc = axis.scatter(issue_time, slba, c=size, cmap='coolwarm', edgecolor='none', alpha=0.5)
    axis.set_title(title)
    axis.set_xlabel('Issue Time')
    axis.set_ylabel('LBA')
    fig.colorbar(sc, ax=axis, label='Size(KB)')

def calcStatistics(df):
# amount of Read/Write IOs

    ios = len(df)
    read_MB = (df[df['cmd_type'] == 'READ']['len'] + 1).sum() * 4 / 1024
    write_MB = (df[df['cmd_type'] == 'WRITE']['len'] + 1).sum() * 4 / 1024
    read_chunk = (df[df['cmd_type'] == 'READ']['len'] + 1).mean() * 4
    write_chunk = (df[df['cmd_type'] == 'WRITE']['len'] + 1).mean() * 4

    read_latavg = df[df['cmd_type'] == 'READ']['latency'].mean()
    read_latmax = df[df['cmd_type'] == 'READ']['latency'].max()
    read_lat99 = df[df['cmd_type'] == 'READ']['latency'].quantile(0.99)
    read_lat999 = df[df['cmd_type'] == 'READ']['latency'].quantile(0.999)
    write_latavg = df[df['cmd_type'] == 'WRITE']['latency'].mean()
    write_latmax = df[df['cmd_type'] == 'WRITE']['latency'].max()
    write_lat99 = df[df['cmd_type'] == 'WRITE']['latency'].quantile(0.99)
    write_lat999 = df[df['cmd_type'] == 'WRITE']['latency'].quantile(0.999)

    read_lat_desc = df[df['cmd_type'] == 'READ']['latency'].describe().to_string(float_format="{:.3f}".format)
    write_lat_desc = df[df['cmd_type'] == 'WRITE']['latency'].describe().to_string(float_format="{:.3f}".format)


    ret = 'Statistics\n'
    ret += f'Total : {ios} Requests, READ : {read_MB:,.0f} MB({read_chunk:,.0f}KB), WRITE : {write_MB:.1f} MB({write_chunk:.1f}KB)\n'
    ret += f'READ latency avg : {read_latavg:.3f}ms, 99% : {read_lat99:.3f}ms, 99.9% : {read_lat999:.3f}ms, max : {read_latmax:.3f}ms\n'
    ret += f'READ latency describe : {read_lat_desc}\n'
    ret += f'WIRTE latency avg : {write_latavg:.3f}ms, 99% : {write_lat99:.3f}ms, 99.9% : {write_lat999:.3f}ms, max : {write_latmax:.3f}ms\n'
    ret += f'WRITE latency describe : {write_lat_desc}\n'
    
    small_read = (df[df['cmd_type'] == 'READ']['len'] < 16)
    ret += f'small read (<32kb) : {small_read.sum()} ea ({small_read.mean():.2f} %)\n'

    # dsmgmt 열의 값 분포를 Count와 Percentage(%)로 계산
    dsmgmt_counts = df[df['cmd_type'] == 'WRITE']['dsmgmt'].value_counts()  # Count 계산
    dsmgmt_percentage = df[df['cmd_type'] == 'WRITE']['dsmgmt'].value_counts(normalize=True) * 100  # Percentage(%) 계산
    # dsmgmt 값에 따라 len의 총 합계 계산
    dsmgmt_len_sum = df[df['cmd_type'] == 'WRITE'].groupby('dsmgmt')['len'].apply(lambda x: (x + 1).sum())

    # 텍스트로 각 값의 개수와 백분율 출력
    ret += 'Write PID(dsmgmt) distribution (PID : Count : Size)\n'
    for value in dsmgmt_counts.index:
        count = dsmgmt_counts[value]
        percentage = dsmgmt_percentage[value]
        len_sum = dsmgmt_len_sum.get(value, 0)  # len의 총 합계, 없으면 0으로 설정
        write_pid_MB = len_sum * 4 / 1024
        ret += f'-PID {value}: {percentage:.1f}% ({count:,}) : {(write_pid_MB/write_MB * 100):.1f}% ({write_pid_MB:,.0f} MB) : avg chunk {(write_pid_MB * 1024 / count):.1f} KB\n'
    return ret
''' 
    # Average distance between contiguous write requests
    write_requests = df[(df['cmd_type'] == 'WRITE') & (df['issue_time'] >= issue_time_threshold)]

    # Initialize a list to store distances
    distances = []

    # Iterate over the rows to calculate distances
    previous_lba = None

    for index, row in write_requests.iterrows():
        if previous_lba is not None:
            # Calculate distance for the first LBA of this request
            first_lba_distance = abs(row['slba'] - previous_lba)
            distances.append(first_lba_distance)
        else:
            # If this is the first request, no previous distance is added
            first_lba_distance = 0
        
        # For additional LBAs, add distance 1 for each
        additional_lbas_count = row['len'] - 1
        additional_distances = [1] * additional_lbas_count
        distances.extend(additional_distances)
        
        # Update previous LBA to the last LBA of the current request
        previous_lba = row['slba'] + row['len'] - 1

    # Calculate average distance
    average_distance = sum(distances) / len(distances) if distances else 0

    ret += f"Average Distance Between Write Requests: {average_distance}\n"
'''


def main(args):
    input_file = args.input_file
    output_file = args.output_file
    df = pd.read_csv(input_file, header=0)

    # Define kernel boot time and threshold time
    #kernel_boot_time_str = "2024-10-29T17:11:54.268735+09:00"
    #threshold_time_str = "2024-10-30T01:04:28.954722+09:00"

    # Parse the timestamps
    #kernel_boot_time = datetime.strptime(kernel_boot_time_str, "%Y-%m-%dT%H:%M:%S.%f%z")
    #threshold_time = datetime.strptime(threshold_time_str, "%Y-%m-%dT%H:%M:%S.%f%z")

    # Calculate the threshold as seconds since kernel boot
    #issue_time_threshold = (threshold_time - kernel_boot_time).total_seconds()


    result = calcStatistics(df)
    f = open(output_file, 'w')
    f.write(result)
    f.close()
    print(result)

    # 산점도 그래프 그리기
    #fig, (ax1, ax2, ax3, ax4) = plt.subplots(nrows=4, ncols=1, figsize=(12, 12), sharex=True)

    #draw_latencySimple(df, fig, ax1)
    #draw_latency(fig, ax1, df[df['cmd_type'] == 'WRITE'], "Latency - Write")
    #draw_latency(fig, ax2, df[df['cmd_type'] == 'READ'], "Latency - Read")
    #draw_lba(fig, ax1, df[df['cmd_type'] == 'WRITE'], "LBA - Write")
    #draw_lba(fig, ax2, df[df['cmd_type'] == 'READ'], "LBA - Read")

    #draw_column(fig, ax1, df[df['cmd_type'] == 'READ'], 'latency', "Latency - Read")
    #draw_column(fig, ax2, df[df['cmd_type'] == 'WRITE'], 'latency', "Latency - Write")
    #draw_column(fig, ax3, df[df['cmd_type'] == 'READ'], 'slba', "LBA - Read")
    #draw_column(fig, ax4, df[df['cmd_type'] == 'WRITE'], 'slba', "LBA - Write")

    #draw_column(fig, ax3, df, 'qdepth_total', "QDepth")
    
#x axis 5400~5600
#y axis 0 ~ 0.2

    fig, (ax2) = plt.subplots(nrows=1, ncols=1, figsize=(18, 6), sharex=True)
    #draw_column(fig, ax1, df[df['cmd_type'] == 'WRITE'], 'dsmgmt', "PID")
    draw_column(fig, ax2, df[df['cmd_type'] == 'WRITE'], 'slba', "LBA - Write")
    #draw_column_pid(fig, ax3, df[df['cmd_type'] == 'WRITE'], 'slba', "LBA - Write")
    ## 레이아웃 조정
    plt.tight_layout()

    # 그래프를 PNG 파일로 저장
    filename_png = os.path.splitext(output_file)[0] + '.png'
    plt.savefig(filename_png, format='png')
         
'''
    fig, (ax2) = plt.subplots(nrows=1, ncols=1, figsize=(18, 6), sharex=True)
    plt.ylim(0, 200000000) 
    filtered_df = df[(df['issue_time'] >= 5400) & (df['issue_time'] <= 5600)]
    draw_column(fig, ax2, filtered_df[filtered_df['cmd_type'] == 'WRITE'], 'slba', "LBA - Write")
    plt.tight_layout()
    # 그래프를 PNG 파일로 저장
    filename_png = os.path.splitext(output_file)[0] + '_zoomin.png'
    plt.savefig(filename_png, format='png')
'''
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Description of your program")

    # 인수 추가
    parser.add_argument("-i", "--input_file", type=str, help="Input file path")
    parser.add_argument("-o", "--output_file", type=str, help="Output file path")

    # 명령행 인수 파싱
    args = parser.parse_args()

    # main 함수 호출
    main(args)

