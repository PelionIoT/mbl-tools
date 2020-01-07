# Clang tidy checker

The `clang-tidy-check` builds a CMake project which has been configured to use `clang-tidy`.

If any of the `clang-tidy` checks fail, the script will return a non-zero exit code.


# Requirements

The CMake project in question must have the following lines in its `CMakeLists.txt`

```
option(RUN_CODE_CHECKS OFF)
if(RUN_CODE_CHECKS)
    set(CMAKE_CXX_CLANG_TIDY clang-tidy;-checks=*,-clang-analyzer-cplusplus-*,clang-analyzer-*)
endif(RUN_CODE_CHECKS)
```

The `clang-tidy-check.sh` script checks for the presence of the above code and attempts to build the project if true.

You must add any external dependencies for your project in the `Dockerfile`.
Currently the `Dockerfile` only installs the dependencies for the UpdateD project in our `mbl-core` repository.

If you choose to run outside of Docker, then you need to install `cmake`, `clang`, `clang-tidy` and any external dependencies.

You must also provide a `.clang-tidy` file in the root of your project or repository, which specifies the `WarningsAsErrors`
option for all enabled checks. See [our example in mbl-core](https://github.com/ARMmbed/mbl-core)

Note: Our projects require CMake 3.5 or later and a version of `clang` that supports c++17.

# Usage

## Running with docker

Invoke the `run-me.sh` script to run inside a docker container.

```
$ ./run-me.sh --workdir /path/to/your/project
```

This will create a container with the dependencies specified in the `Dockerfile` and run the `clang-tidy` checks.

Output will be printed on screen with the results.

## Running natively

Invoke the `clang-tidy-checks.sh` script directly to run outside of a docker container.

```
$ ./clang-tidy-check.sh --workdir /path/to/your/project
```

Output will be printed on screen with the results.
