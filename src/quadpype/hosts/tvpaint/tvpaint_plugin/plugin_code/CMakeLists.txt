cmake_minimum_required(VERSION 3.17)

project(QuadPypePlugin C CXX)

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

set(BOOST_ROOT "C:/Boost")
set(OPENSSL_INCLUDE "C:/Program Files/OpenSSL-Win64/include")
set(OPENSSL_LIB_DIR "C:/Program Files/OpenSSL-Win64/lib")
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

add_library(${PROJECT_NAME} SHARED library.cpp library.def "${TVPAINT_SDK_LIB}/dllx.c")

target_link_libraries(${PROJECT_NAME} ${Boost_LIBRARIES})
target_link_libraries(${PROJECT_NAME} jsonrpcpp)
