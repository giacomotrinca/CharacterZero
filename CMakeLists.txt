cmake_minimum_required(VERSION 3.20)
project(CharacterZero CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

include(FetchContent)

FetchContent_Declare(
    httplib
    GIT_REPOSITORY https://github.com/yhirose/cpp-httplib.git
    GIT_TAG v0.18.1
    GIT_SHALLOW TRUE
)

FetchContent_Declare(
    json
    GIT_REPOSITORY https://github.com/nlohmann/json.git
    GIT_TAG v3.11.3
    GIT_SHALLOW TRUE
)

set(SQLITECPP_RUN_CPPLINT  OFF CACHE BOOL "" FORCE)
set(SQLITECPP_RUN_CPPCHECK OFF CACHE BOOL "" FORCE)
set(SQLITECPP_INTERNAL_SQLITE ON  CACHE BOOL "" FORCE)
FetchContent_Declare(
    SQLiteCpp
    GIT_REPOSITORY https://github.com/SRombauts/SQLiteCpp.git
    GIT_TAG 3.3.2
    GIT_SHALLOW TRUE
)

FetchContent_MakeAvailable(httplib json SQLiteCpp)

add_executable(CharacterZero
    src/main.cpp
    src/server/Router.cpp
    src/db/Database.cpp
    src/domain/Sheet.cpp
    src/domain/SheetRepository.cpp
    src/domain/Schema.cpp
)

target_include_directories(CharacterZero PRIVATE src)

target_link_libraries(CharacterZero PRIVATE
    httplib::httplib
    nlohmann_json::nlohmann_json
    SQLiteCpp
)

target_compile_definitions(CharacterZero PRIVATE
    CZ_WEB_ROOT="${CMAKE_SOURCE_DIR}/web"
    CZ_DATA_DIR="${CMAKE_SOURCE_DIR}/data"
    CZ_MIGRATIONS_DIR="${CMAKE_SOURCE_DIR}/src/db/migrations"
)

if(MSVC)
    target_compile_options(CharacterZero PRIVATE /W4)
else()
    target_compile_options(CharacterZero PRIVATE -Wall -Wextra -Wpedantic)
endif()
