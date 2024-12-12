README for the TVPaint QuadPype plugin
================================

Introduction
------------

This project is dedicated to the integration of QuadPype functionalities in TVPaint.
This implementation relies on the creation and usage of a built TVPaint plugin (C/C++) which can communicate with our python process.
The communication should allow triggering tools or pipeline functions from TVPaint
and accept requests from the QuadPype python process at the same time.

The current implementation is based on websocket protocol, using json-rpc communication (specification 2.0). Project is in beta stage, tested only on Windows.

To be able to load plugin, environment variable `QUADPYPE_WEBSOCKET_URL` must be set otherwise plugin won't load at all. Plugin should not affect TVPaint if python server crash, but buttons won't work.

## Requirements for the Plugin Compilation
- TVPaint SDK - Ask for SDK on TVPaint support.
- Boost `1.86.0` - Boost is used across other plugins
- Websocket++/Websocketpp `0.8.2` - Websocket library (https://github.com/zaphoyd/websocketpp)
- OpenSSL's library `3.4.0` - Required by Websocketpp, download and install from [Shining Light Productions](https://slproweb.com/products/Win32OpenSSL.htm)
- jsonrpcpp `1.4.0` - C++ library handling json-rpc 2.0 (https://github.com/badaix/jsonrpcpp)

# Plugin Compilation

Edit the CMakeLists.txt to edit:
- The paths to the TV Paint SDK `include` and `lib` folders.
- The path to the OpenSSL library (if you haven't it installed in the already set path)

Then, follow the steps from [this tutorial](https://github.com/BenSouchet/compile-tvpaint-plugin).

To ensure the `./dependencies/` folder is properly found, execute the cmake command from the `plugin_code` directory (use `cd` to navigate to that location before execution the commands).

## TODO

- Modify code and CMake to be able to compile on macOS/Linux
- Separate the websocket logic from the plugin logic
- Hide the buttons and show an error message if the server is closed
