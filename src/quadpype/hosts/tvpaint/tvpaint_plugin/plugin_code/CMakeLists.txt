cmake_minimum_required(VERSION 3.17)

cmake_policy(SET CMP0144 NEW)
cmake_policy(SET CMP0167 NEW)

project(QuadPypePlugin C CXX)

set(CUR_TARGET ${PROJECT_NAME})
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(IP_ENABLE_UNICODE OFF)
set(IP_ENABLE_DOCTEST OFF)

set(CMAKE_CONFIGURATION_TYPES "Release" CACHE STRING "" FORCE)

if(MSVC)
    set(CMAKE_WINDOWS_EXPORT_ALL_SYMBOLS ON)
    add_definitions(-D_CRT_SECURE_NO_WARNINGS)
    # Define WIN64 or WIN32 for TVPaint SDK
    if(CMAKE_SIZEOF_VOID_P EQUAL 8)
        message("64bit")
        add_definitions(-DWIN64)
    elseif(CMAKE_SIZEOF_VOID_P EQUAL 4)
        message("32bit")
        add_definitions(-DWIN32)
    endif()
endif()

set(BOOST_ROOT "ADD_YOUR_PATH_TO_THE/boost_build")
set(OPENSSL_INCLUDE "ADD_YOUR_PATH_TO_THE/openssl/include")
set(OPENSSL_LIB_DIR "ADD_YOUR_PATH_TO_THE/openssl/lib")
set(WEBSOCKETPP_INCLUDE "./dependencies/websocketpp-0.8.2/")
set(JSONRPCPP_INCLUDE "./dependencies/jsonrpcpp-1.4.0/include")
set(TVPAINT_SDK_INCLUDE "ADD_YOUR_PATH_TO_THE/TVPaint_SDK/include")
set(TVPAINT_SDK_LIB "ADD_YOUR_PATH_TO_THE/TVPaint_SDK/lib")

# Use static boost libraries
set(Boost_USE_STATIC_LIBS ON)

find_package(Boost COMPONENTS random chrono date_time regex REQUIRED)

include_directories(
        "${TVPAINT_SDK_INCLUDE}"
        "${OPENSSL_INCLUDE}"
        "${WEBSOCKETPP_INCLUDE}"
        "${JSONRPCPP_INCLUDE}"
        "${Boost_INCLUDE_DIRS}"
)

link_directories(
        "${OPENSSL_LIB_DIR}"
        "${Boost_LIBRARY_DIRS}"
)

add_library(jsonrpcpp INTERFACE)


if(WIN32)
    add_library(${PROJECT_NAME} SHARED library.cpp library.def "${TVPAINT_SDK_LIB}/dllx.c")
elseif(APPLE)
    add_library(${PROJECT_NAME} MODULE library.cpp library.def "${TVPAINT_SDK_LIB}/dllx.c")
elseif(UNIX)
    message(STATUS "Building for Linux/Unix")
endif()

target_link_libraries(${PROJECT_NAME} ${Boost_LIBRARIES})
target_link_libraries(${PROJECT_NAME} jsonrpcpp)

if(APPLE)
    set_target_properties(${PROJECT_NAME} PROPERTIES
        BUNDLE TRUE
        MACOSX_BUNDLE TRUE
        MACOSX_BUNDLE_GUI_IDENTIFIER fr.tvpaint.tvpa.QuadPypePlugin
        MACOSX_BUNDLE_BUNDLE_NAME ${PROJECT_NAME}
        MACOSX_BUNDLE_BUNDLE_VERSION "1.0"
        MACOSX_BUNDLE_SHORT_VERSION_STRING "1.0"
        OUTPUT_NAME ${PROJECT_NAME}
        MACOSX_BUNDLE_INFO_PLIST "./Info.plist"
    )
endif()
