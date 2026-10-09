cmake_minimum_required(VERSION 3.24)
project(itb_engine LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
  set(CMAKE_BUILD_TYPE RelWithDebInfo CACHE STRING "" FORCE)
endif()

include(cmake/Dependencies.cmake)

# Where the game's shipped files live. Game files are never committed; the
# default points at the git-ignored local copy of the Linux build.
get_filename_component(ITB_REPO_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/.." ABSOLUTE)
set(ITB_DEFAULT_GAME_DIR "${ITB_REPO_ROOT}/.local_decompile/builds/linux_21601364"
    CACHE PATH "Default game root (directory containing scripts/)")

add_library(itb_engine
  src/core.cpp
  src/symbols.cpp
  src/board.cpp
  src/lua_env.cpp
  src/game_data.cpp
  src/recording.cpp
  src/format.cpp
  src/movement.cpp
  src/tile_rules.cpp
  src/tile_status.cpp
  src/space_damage.cpp
)
target_include_directories(itb_engine PUBLIC include PRIVATE src)
target_link_libraries(itb_engine PRIVATE itb_lua nlohmann_json::nlohmann_json)
target_compile_definitions(itb_engine PRIVATE
  ITB_DEFAULT_GAME_DIR="${ITB_DEFAULT_GAME_DIR}")
# No fused multiply-add: A* path choice depends on the game's exact float32
# rounding (movement.cpp).
target_compile_options(itb_engine PRIVATE -Wall -Wextra -Wpedantic -ffp-contract=off)

add_executable(itb_inspect tools/itb_inspect.cpp)
target_link_libraries(itb_inspect PRIVATE itb_engine nlohmann_json::nlohmann_json)

enable_testing()
add_executable(itb_tests
  tests/test_main.cpp
  tests/test_core.cpp
  tests/test_board.cpp
  tests/test_game_data.cpp
  tests/test_recording.cpp
  tests/test_movement.cpp
  tests/test_tile_rules.cpp
)
target_link_libraries(itb_tests PRIVATE itb_engine doctest::doctest)
target_compile_definitions(itb_tests PRIVATE
  ITB_REPO_ROOT="${ITB_REPO_ROOT}"
  ITB_FIXTURE_DIR="${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures")
add_test(NAME itb_tests COMMAND itb_tests)
