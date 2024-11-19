#!/bin/bash

DATE=$(date +%y%m%d)

## DEVICE PARAMs ##
# DEV_NAME=nvme1n1 #SHGP31-1000GM
# DEV_SIZE=931
DEV_NAME=nvme2n1 # samsung 980
DEV_SIZE=465
TRACE_DEV_NAME=nvme1n1 #SK p31
TRACE_DEV_SIZE=931
######
DEV_TARGET=${DEV_NAME}

## FS params ##
FS_DIR=/mnt/f2fs
#S4_MODULE=/home/ihhwang/gc_scanning/F2FS_S4/linux-6.6.52/fs/f2fs/f2fs_S4_locality.ko
#S4_MODULE=/home/ihhwang/gc_scanning/F2FS_S4/linux-6.6.52/fs/f2fs/f2fs_entropy_v3.ko
S4_MODULE=/home/ihhwang/gc_scanning/F2FS_S4/linux-6.6.52/fs/f2fs/f2fs_entropy_v4.ko
H3=/home/ihhwang/gc_scanning/F2FS_S4/linux-6.6.52/fs/f2fs/f2fs_entropy_h3.ko
ORIG_F2FS_MODULE=/home/ihhwang/linux-6.6.52/fs/f2fs/f2fs_vanilla.ko
##

## WORKLOADS PARAMs ##
#BASE_SIZE=465
BASE_SIZE=50
UTIL=50 # in %
THREADS=16
MAX_VICTIM_SEARCH=4096
IOF=300 #IOSIZE FACTOR in percent # IO_SIZE/BASE_SIZE
#IOF=135 #IOSIZE FACTOR in percent # IO_SIZE/BASE_SIZE
####
SIZE=$((${BASE_SIZE}*1024)) # in MB

## MODEs ##
S4_ENABLE=0
LFS_MODE=0
PARTITION_ENABLE=1
######

CAT_PID=0
DSTAT_PID=0

echo Check the device...
if [ "$(( $(cat /sys/block/${DEV_NAME}/size) * 512 / 1024 / 1024 / 1024 ))" -eq ${DEV_SIZE} ];
then
  echo "Proper device"
else
  echo "This is not proper device. Check device name: ${DEV_NAME}."
  echo "${DEV_NAME} is $(( $(cat /sys/block/${DEV_NAME}/size) * 512 / 1024 / 1024 / 1024 ))GB but the you set ${DEV_SIZE}GB."
  exit
fi

echo Check the trace device...
if [ "$(( $(cat /sys/block/${TRACE_DEV_NAME}/size) * 512 / 1024 / 1024 / 1024 ))" -eq ${TRACE_DEV_SIZE} ];
then
  echo "Proper device"
else
  echo "This is not proper device. Check trace device name: ${TRACE_DEV_NAME}."
  echo "${TRACE_DEV_NAME} is $(( $(cat /sys/block/${TRACE_DEV_NAME}/size) * 512 / 1024 / 1024 / 1024 ))GB but the you set ${TRACE_DEV_SIZE}GB."
  exit
fi


if [ "$LFS_MODE" -eq "1" ]; then
  echo "lfs mode enabled"
  MODE=lfs
else
  echo "adaptive mode"
  MODE=adaptive
fi


function test {
 echo test
}

function error_exit {
  if [ $? -ne 0 ]; then 
    exit 1 
  fi

}

function mk_partition {
  echo make partition
  (
  echo n
  echo p
  echo
  echo
  echo +${SIZE}M
  echo w
  ) | fdisk /dev/${DEV_NAME}
  error_exit
  partprobe /dev/${DEV_NAME}
} 

function rm_partition {
  echo remove partition
  (
  echo d
  echo
  echo w
  ) | fdisk /dev/${DEV_NAME}
  partprobe /dev/${DEV_NAME}
} 

function f2fs_init {
  if [ "$PARTITION_ENABLE" -eq "1" ]; then
    echo "SSD partition (${BASE_SIZE}GB) enabled"
    mk_partition
    DEV_TARGET=${DEV_NAME}p1
  else
    BASE_SIZE=${DEV_SIZE}
    SIZE=$((${BASE_SIZE}*1024)) # in MB
    echo "Use total dev size (${BASE_SIZE}GB)"
    DEV_TARGET=${DEV_NAME}
  fi

  if [ "$S4_ENABLE" -eq "1" ]; then
    #F2FS_MODULE_DIR=${S4_MODULE_DIR}
    #echo "S4 enabled. module dir: ${F2FS_MODULE_DIR}"
    F2FS_MODULE=${S4_MODULE}
    echo "S4 enabled. module path: ${F2FS_MODULE}"
  else
    #F2FS_MODULE_DIR=${ORIG_F2FS_MODULE_DIR}
    #echo "S4 disabled. Use original F2FS. module dir: ${F2FS_MODULE_DIR}"
    F2FS_MODULE=${ORIG_F2FS_MODULE}
    echo "S4 disabled. Use original F2FS. module path: ${F2FS_MODULE}"
  fi
  #echo "Module updated at $(ls -l ${F2FS_MODULE_DIR}/f2fs.ko | awk '{print $6, $7, $8}')"
  echo "Module updated at $(ls -l ${F2FS_MODULE} | awk '{print $6, $7, $8}')"

  echo "Target device: ${DEV_TARGET}"
  #insmod ${F2FS_MODULE_DIR}/f2fs.ko
  insmod ${F2FS_MODULE}
  error_exit
  mkfs.f2fs -f /dev/${DEV_TARGET}
  error_exit
  mount -o mode=${MODE} /dev/${DEV_TARGET} ${FS_DIR}
  error_exit

#  mkfs.f2fs -f -s 512 ${DEV_PART}
}

function f2fs_exit {
  umount ${FS_DIR}
  rmmod f2fs
  if [ "$PARTITION_ENABLE" -eq "1" ]; then
    rm_partition
  fi
}

function calc_file_size {
  echo $((${SIZE}*${UTIL}/100/${THREADS}))
} 

function fio_warmup {
fio --name=fio --directory=${FS_DIR} --rw=write --bs=128K \
  --size=${FILE_SIZE}M --numjobs=${THREADS} --group_reporting
}

function fio_run_zipf {
  (
  fio --name=fio --directory=${FS_DIR} --rw=randwrite --bs=4K \
    --norandommap --numjobs=${THREADS} --random_distribution=zipf:${THETA} \
    --filesize=${FILE_SIZE}M --io_size=$((${SIZE}*${IOF}/100/${THREADS}))M \
    --group_reporting \
    --output=${PREFIX}test_part${BASE_SIZE}G_${MODE}_util${UTIL}_S4_${S4_ENABLE}_zipf${THETA}_${MAX_VICTIM_SEARCH}segs_${DATE}.txt \
    --eta=always --eta-newline=500msec 
    ) | tee ${PREFIX}eta_part${BASE_SIZE}G_${MODE}_util${UTIL}_S4_${S4_ENABLE}_zipf${THETA}_${MAX_VICTIM_SEARCH}segs_${DATE}.txt
}
    #--filesize=${FILE_SIZE}M --io_size=$((${SIZE}*${IOF}/100/${THREADS}-${FILE_SIZE}))M \
    #--norandommap --numjobs=${THREADS} --random_distribution=zipf:${THETA} \
    #--filesize=${FILE_SIZE}M --io_size=$((40960-${FILE_SIZE}))M \
    #--norandommap --numjobs=${THREADS} --random_distribution=zipf:${THETA} \

function fio_run_uniform {
  (
  fio --name=fio --directory=${FS_DIR} --rw=randwrite --bs=4K \
    --norandommap --numjobs=${THREADS} \
    --filesize=${FILE_SIZE}M --io_size=$((${SIZE}*${IOF}/100/${THREADS}-${FILE_SIZE}))M \
    --group_reporting \
    --output=${PREFIX}test_part${BASE_SIZE}G_${MODE}_util${UTIL}_S4_${S4_ENABLE}_uniform_${MAX_VICTIM_SEARCH}segs_${DATE}.txt \
    --eta=always --eta-newline=500msec 
    ) | tee ${PREFIX}eta_part${BASE_SIZE}G_${MODE}_util${UTIL}_S4_${S4_ENABLE}_uniform_${MAX_VICTIM_SEARCH}segs_${DATE}.txt
}

function trace_off {
  echo 0 > /sys/kernel/tracing/events/nvme/nvme_setup_cmd/enable
  echo 0 > /sys/kernel/tracing/events/nvme/nvme_complete_rq/enable

  echo 0 > /sys/kernel/tracing/tracing_on

  echo 1 > /sys/kernel/tracing/buffer_size_kb
  error_exit
  echo 144 > /sys/kernel/tracing/buffer_size_kb
  error_exit

  echo "kill cat and dstat process"
  if [ $CAT_PID -ne 0 ]; then
    kill -9 $CAT_PID
    CAT_PID=0
  fi
  if [ $DSTAT_PID -ne 0 ]; then
    kill -9 $DSTAT_PID
    DSTAT_PID=0
  fi
}

function trace_on {

  echo 1 > /sys/kernel/tracing/buffer_size_kb
  error_exit
  echo 144 > /sys/kernel/tracing/buffer_size_kb
  error_exit

  echo 1 > /sys/kernel/tracing/events/nvme/nvme_setup_cmd/enable
  echo 1 > /sys/kernel/tracing/events/nvme/nvme_complete_rq/enable

  echo 1 > /sys/kernel/tracing/tracing_on
  
  if [ $(mount | grep -c "${TRACE_DEV_NAME}") -eq 0 ]; then
    mount /dev/${TRACE_DEV_NAME} /mnt/data2
    error_exit
  fi
  cat /sys/kernel/tracing/trace_pipe | grep ${DEV_NAME} > /mnt/data2/${RESULT}_ftrace.txt &
  CAT_PID=$?
  error_exit

  dstat -D ${DEV_NAME} -d > /mnt/data2/${RESULT}_dstat.txt &
  DSTAT_PID=$?
}
#PID=108322
#WAIT_TIME=600
#while kill -0 $PID 2>/dev/null; do
#  echo waiting...
#  sleep $WAIT_TIME  # Check every 1 second
#done

echo "start script"
trace_off
#sudo mount /dev/nvme1n1 /mnt/data2
#error_exit

#PREFIX=F2FS_300_nowarm
PREFIX=DEBUG_
#UTIL=50
#for MAX_VICTIM_SEARCH in 1 4 16 64 256 1024 4096 16384 65536 262144


#PREFIX=ENTROPY_V3_NODE_
for UTIL in 50
do
for THETA in 0.5
do
for S4_ENABLE in 1
do
for MAX_VICTIM_SEARCH in 4096
do
echo ${MAX_VICTIM_SEARCH} segs

f2fs_exit

echo 3 > /proc/sys/vm/drop_caches
nvme format /dev/${DEV_NAME} --force -s 1
sleep 3

#PREFIX=ENTROPY_V2_
f2fs_init

echo ${MAX_VICTIM_SEARCH} > /sys/fs/f2fs/${DEV_TARGET}/max_victim_search #default 4096
error_exit

FILE_SIZE=$(calc_file_size)
sleep 3

trace_off
trace_on

#fio_warmup
#error_exit

#uniform random distribution
if [ "$(echo "$THETA == -1" | bc -l)" -eq 1 ]; then
#if [ $THETA -eq -1 ]; then
fio_run_uniform
#zipfian distribution of theta $THETA
else
fio_run_zipf

cat /sys/kernel/debug/f2fs/status > ${PREFIX}_${MAX_VICTIM_SEARCH}segs_S4_${S4_ENABLE}_${DATE}.status

fi
#fio_run_zipf_nowarm
error_exit
#pkill  cat
done
done
done
done

trace_off
