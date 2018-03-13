mkdir src
cd src

IF "%PYTHON_ARCH%" == "32" (
  set OPENSSL_DIR="C:\OpenSSL-Win32"
) ELSE (
  set OPENSSL_DIR="C:\OpenSSL-Win64"
)

ls %OPENSSL_DIR%\lib
ls %OPENSSL_DIR%\lib\VC
ls %OPENSSL_DIR%\lib\VC\static

IF "%MSVC%" == "Visual Studio 9" (
   ECHO "Building without platform set"
   cmake ..\libssh2 -G "NMake Makefiles"        ^
   	 -DCMAKE_BUILD_TYPE=Release             ^
	 -DCRYPTO_BACKEND=OpenSSL               ^
	 -DBUILD_SHARED_LIBS=OFF                ^
	 -DENABLE_ZLIB_COMPRESSION=ON           ^
	 -DENABLE_CRYPT_NONE=ON                 ^
	 -DENABLE_MAC_NONE=ON                   ^
	 -DZLIB_LIBRARY=C:/zlib/lib/zlib.lib    ^
	 -DZLIB_INCLUDE_DIR=C:/zlib/include     ^
	 -DOPENSSL_ROOT_DIR=%OPENSSL_DIR%
REM	 -DOPENSSL_MSVC_STATIC_RT=TRUE
REM 	 -DOPENSSL_USE_STATIC_LIBS=TRUE
) ELSE (
   ECHO "Building with platform %MSVC%"
   cmake ..\libssh2 -G "NMake Makefiles"        ^
   	 -DCMAKE_BUILD_TYPE=Release             ^
	 -DCRYPTO_BACKEND=OpenSSL               ^
	 -G"%MSVC%"                             ^
	 -DBUILD_SHARED_LIBS=OFF                ^
	 -DENABLE_ZLIB_COMPRESSION=ON           ^
	 -DENABLE_CRYPT_NONE=ON                 ^
	 -DENABLE_MAC_NONE=ON                   ^
	 -DZLIB_LIBRARY=C:/zlib/lib/zlib.lib    ^
	 -DZLIB_INCLUDE_DIR=C:/zlib/include     ^
	 -DOPENSSL_ROOT_DIR=%OPENSSL_DIR%
REM	 -DOPENSSL_MSVC_STATIC_RT=TRUE
REM	 -DOPENSSL_USE_STATIC_LIBS=TRUE
)

cp %OPENSSL_DIR%\lib\VC\libeay32MD.lib %APPVEYOR_BUILD_FOLDER%
cp %OPENSSL_DIR%\lib\VC\ssleay32MD.lib %APPVEYOR_BUILD_FOLDER%
REM cp %OPENSSL_DIR%\libeay32.dll %APPVEYOR_BUILD_FOLDER%\ssh2\
REM cp %OPENSSL_DIR%\ssleay32.dll %APPVEYOR_BUILD_FOLDER%\ssh2\

cmake --build . --config Release
cd ..
ls
ls pssh
ls src/src
cp src/src/libssh2.lib %PYTHON%/libs/ || cp src/src/Release/libssh2.lib %PYTHON%/libs/
ls %PYTHON%/libs/
