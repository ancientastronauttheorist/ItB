include(FetchContent)

# Lua 5.1.5: the version the game embeds. Used to run the game's own scripts
# (pawn/weapon definitions) from the local install; the scripts themselves are
# never committed.
FetchContent_Declare(lua51
  URL https://www.lua.org/ftp/lua-5.1.5.tar.gz
  URL_HASH SHA256=2640fc56a795f29d28ef15e13c34a47e223960b0240e8cb0a82d9b0738695333
  DOWNLOAD_EXTRACT_TIMESTAMP TRUE)
FetchContent_MakeAvailable(lua51)

file(GLOB ITB_LUA_SOURCES "${lua51_SOURCE_DIR}/src/*.c")
list(REMOVE_ITEM ITB_LUA_SOURCES
  "${lua51_SOURCE_DIR}/src/lua.c"
  "${lua51_SOURCE_DIR}/src/luac.c"
  "${lua51_SOURCE_DIR}/src/print.c")
add_library(itb_lua STATIC ${ITB_LUA_SOURCES})
target_include_directories(itb_lua PUBLIC "${lua51_SOURCE_DIR}/src")
target_compile_definitions(itb_lua PRIVATE LUA_USE_POSIX)
set_target_properties(itb_lua PROPERTIES C_STANDARD 99)
target_compile_options(itb_lua PRIVATE -w)

FetchContent_Declare(doctest
  URL https://github.com/doctest/doctest/archive/refs/tags/v2.4.11.tar.gz
  URL_HASH SHA256=632ed2c05a7f53fa961381497bf8069093f0d6628c5f26286161fbd32a560186
  DOWNLOAD_EXTRACT_TIMESTAMP TRUE)
FetchContent_GetProperties(doctest)
if(NOT doctest_POPULATED)
  FetchContent_Populate(doctest)
endif()
add_library(doctest INTERFACE)
add_library(doctest::doctest ALIAS doctest)
target_include_directories(doctest INTERFACE "${doctest_SOURCE_DIR}")

FetchContent_Declare(nlohmann_json
  URL https://github.com/nlohmann/json/releases/download/v3.11.3/json.tar.xz
  URL_HASH SHA256=d6c65aca6b1ed68e7a182f4757257b107ae403032760ed6ef121c9d55e81757d
  DOWNLOAD_EXTRACT_TIMESTAMP TRUE)
FetchContent_MakeAvailable(nlohmann_json)
