// itb_live: the engine side of live play (scripts/live_play.py). See
// live_tool.hpp for the requests and live_tool.cpp for the command line.
#include "live_tool.hpp"

int main(int argc, char** argv) { return itb::tools::run_live(argc, argv); }
