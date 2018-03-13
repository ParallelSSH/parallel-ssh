mkdir zlib_build && cd zlib_build

IF "%MSVC%" == "Visual Studio 9" (
   ECHO "Building without platform set"
   cmake ..\zlib-1.2.11 -G "NMake Makefiles"        ^
       -DCMAKE_INSTALL_PREFIX="C:\zlib"             ^
       -DCMAKE_BUILD_TYPE=Release                   ^
       -DBUILD_SHARED_LIBS=OFF
) ELSE (
   ECHO "Building with platform %MSVC%"
   cmake ..\zlib-1.2.11                             ^
       -G"%MSVC%"                                   ^
       -DCMAKE_INSTALL_PREFIX="C:\zlib"             ^
       -DCMAKE_BUILD_TYPE=Release                   ^
       -DBUILD_SHARED_LIBS=OFF
)

cmake --build . --config Release --target install
cp C:/zlib/lib/zlibstatic.lib %PYTHON%/libs/
cd ..
ls %PYTHON%/libs/
