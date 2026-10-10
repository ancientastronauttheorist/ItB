// itb_inspect --solve: the stage 9 search on recorded boards.
#pragma once

#include <cstdint>
#include <filesystem>
#include <string>

namespace itb::tools {

struct SolveToolOptions {
  std::filesystem::path target;  // a recording, or a directory of them
  std::filesystem::path game;
  double time_limit = 10.0;
  uint64_t node_limit = 0;
  int threads = 1;  // search threads (one engine each)
  int beam = -1;    // beam width (-1: the solver's default)
  int sample = 0;  // directory: this many evenly spaced boards (0 = all)
  int shard = 0;   // directory: boards i with i % shards == shard
  int shards = 1;
  bool verbose = false;            // directory: print every plan
  std::filesystem::path json_out;  // one JSON line per board
  bool lua_counts = false;         // print Lua calls by table and method at the end
};

int run_solve(const SolveToolOptions& options);

}  // namespace itb::tools
