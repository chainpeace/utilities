#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <unordered_map>
#include <fcntl.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <cstdint>
#include <chrono>
#include <vector>
#include <thread>

#define DEBUG 0
#define NUM_TH 3

// Function to perform a file system operation
int performOperation(int iterate, long line_num, const std::string& operation, const std::string& filePath, 
                      uint64_t offset = 0, uint64_t size = 0, const std::string& data = "") {
    if (operation == "OPEN") {
        int fd = open(filePath.c_str(), O_CREAT | O_RDWR, 0644);
        if (fd < 0) {
#if DEBUG
            perror("Error opening file");
#endif
        } else {
#if DEBUG
            std::cout << "File opened: " << filePath << "\n";
#endif
            close(fd);
        }
    } else if (operation == "READ") {
        int fd = open(filePath.c_str(), O_RDONLY);
        if (fd < 0) {
#if DEBUG
            perror("Error opening file for read");
#endif
        } else {
            char* buffer = new char[size];
            if (pread(fd, buffer, size, offset) < 0) {
                std::cout << "iterate: " << iterate << ", line: " << line_num << "Reading error" << std::endl;
                perror("Error reading file");
                if (errno == ENOSPC)
                  return errno;
            } else {
#if DEBUG
                std::cout << "Read " << size << " bytes from " << filePath 
                          << " at offset " << offset << "\n";
#endif
            }
            delete[] buffer;
            close(fd);
        }
    } else if (operation == "WRITE") {
        int fd = open(filePath.c_str(), O_WRONLY | O_CREAT, 0644);
        if (fd < 0) {
#if DEBUG
            perror("Error opening file for write");
#endif
        } else {
            if (pwrite(fd, data.c_str(), size, offset) < 0) {
                std::cout << "iterate: " << iterate << ", line: " << line_num << "Writing error" << std::endl;
                perror("Error writing to file");
                if (errno == ENOSPC)
                  return errno;
            } else {
#if DEBUG
                std::cout << "Wrote " << size << " bytes to " << filePath 
                          << " at offset " << offset << "\n";
#endif
            }
            close(fd);
        }
    } else if (operation == "CLOSE") {
#if DEBUG
        std::cout << "CLOSE is simulated. Explicit file close handled in other operations.\n";
#endif
    } else if (operation == "FSYNC" || operation == "FDATASYNC") {
        int fd = open(filePath.c_str(), O_WRONLY);
        if (fd < 0) {
#if DEBUG
            perror("Error opening file for sync");
#endif
        } else {
            if (fsync(fd) < 0) {
                std::cout << "iterate: " << iterate << ", line: " << line_num << "Sync error" << std::endl;
                perror("Error syncing file");
                if (errno == ENOSPC)
                  return errno;
            } else {
#if DEBUG
                std::cout << "Synced file: " << filePath << "\n";
#endif
            }
            close(fd);
        }
    }
  return 0;
}

// Parse and replay trace line
bool parseAndReplayTraceLine(const std::string& line, const std::string& baseDir, int thread_idx, long line_num) {
    std::istringstream iss(line);
    int seqNum;
    std::string ts, operation;
    uint64_t inodeNum, inodeSize, offset = 0, size = 0;
    std::string tag;
    int ret;

    // Read basic fields
    if (!(iss >> seqNum >> ts >> operation >> inodeNum >> inodeSize)) {
        std::cerr << "Error: Malformed trace line: " << line << "\n";
        return false;
    }

    // File path simulation
    std::string filePath;
    filePath = baseDir + "/inode_" + std::to_string(inodeNum) + "_" + std::to_string(thread_idx)  + ".dat";

    // Handle READ and WRITE separately
    if (operation == "READ" || operation == "WRITE") {
      if (!(iss >> offset >> size)) {
        std::cerr << "Error: Malformed READ/WRITE line: " << line << "\n";
        return false;
      }

      if (operation == "READ") {
        ret = performOperation(thread_idx, line_num, "READ", filePath, offset, size);
      } else if (operation == "WRITE") {
        std::string data(size, 'x'); // Example: filling with 'x'
        ret = performOperation(thread_idx, line_num, "WRITE", filePath, offset, size, data);
      }
    } else {
      ret = performOperation(thread_idx, line_num, operation, filePath);
    }
    if (ret == ENOSPC)
      return false;

    return true;
}

int run_trace(int argc, char* argv[]) {
  if (argc < 4) {
    std::cerr << "Usage: " << argv[0] << " <trace file> <base directory>\n";
    return 1;
  }
  int thread_idx = (intptr_t)((argv[3]));

  auto start_time = std::chrono::system_clock::now();
  
// error line 143302145, iter 2
  
  for (int i = 0; i < 2; i++) {
    //    std::cout << "Iteration " << i << " started " <<  ((std::chrono::nanoseconds)(start_time)).count() / 1000000000L << std::endl;

    std::ifstream traceFile(argv[1]);
    std::string baseDir = argv[2];
    if (!traceFile.is_open()) {
      std::cerr << "Error: Could not open trace file " << argv[1] << "\n";
      return 1;
    }

    std::string line;
    long line_num = 0;
    // Read and process the trace file line by line
    while (std::getline(traceFile, line)) {
      if (line.empty()) continue; // Skip empty lines
      line_num++;
      if (!parseAndReplayTraceLine(line, baseDir, thread_idx, line_num)) {
        std::cerr << "Error: Failed to process trace line.\n";
        return 1;
      }

      if (line_num % 10000000 == 0) {
        auto now_time = std::chrono::system_clock::now();
        std::cout << "Thead idx: " << thread_idx << " Iteration: " << i << " line number: " << line_num << " elapsed time: " <<  ((std::chrono::nanoseconds)(now_time - start_time)).count() / 1000000000L << std::endl;

      }
      if (line_num >= (270000000 - thread_idx * 40000000))
        break;
    }

    auto now_time = std::chrono::system_clock::now();
    std::cout << "Thead idx:"<< thread_idx <<" Iteration " << i << " end. line number: " << line_num << " elapsed time: " <<  ((std::chrono::nanoseconds)(now_time - start_time)).count() / 1000000000L << std::endl;
    traceFile.close();
    system("cat /sys/kernel/debug/f2fs/status");
  }
  std::cout << "Trace replay completed successfully.\n";
  return 0;
}

int main(int argc, char* argv[]) {

  if (argc < 3) {
    std::cerr << "Usage: " << argv[0] << " <trace file> <base directory>\n";
    return 1;
  }

  std::vector<std::thread> threads;
  char *argv2s[NUM_TH][4];

  for (intptr_t i = 0 ; i < NUM_TH ; i++) {
    argv2s[i][0] = argv[0];
    argv2s[i][1] = argv[1];
    argv2s[i][2] = argv[2];
    argv2s[i][3] = (char*)i;
    threads.emplace_back(run_trace, argc+1, argv2s[i]);
  }

  for (auto& t : threads) {
    t.join();
  }
  return 0;

}
