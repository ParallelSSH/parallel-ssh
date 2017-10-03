mkdir src && cd src

IF "%MSVC%" == "Visual Studio 9" (
   ECHO "Building without platform set"
   cmake ..\libssh2 -G "NMake Makefiles"        ^
   	 -DCMAKE_BUILD_TYPE=Release             ^
	 -DCRYPTO_BACKEND=WinCNG                ^
	 -DBUILD_SHARED_LIBS=OFF
) ELSE (
   ECHO "Building with platform %MSVC%"
   cmake ..\libssh2 -G "NMake Makefiles"        ^
   	 -DCMAKE_BUILD_TYPE=Release             ^
	 -DCRYPTO_BACKEND=WinCNG                ^
	 -G"%MSVC%"                             ^
	 -DBUILD_SHARED_LIBS=OFF
)

cmake --build . --config Release
cd ..
ls src/src
cp src/src/libssh2.lib %PYTHON%/libs/ || cp src/src/Release/libssh2.lib %PYTHON%/libs/
ls %PYTHON%/libs/
