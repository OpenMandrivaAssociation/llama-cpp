# For the extra python package gguf that comes with llama-cpp
%global pypi_name gguf
%global pypi_version 0.10.0
%define soversion %(echo %{version}|sed -e 's,^[a-z],,')
%global backend_dir %{_libdir}/ggml

# Some optional subpackages
%bcond_without examples
%if %{with examples}
%global build_examples ON
%else
%global build_examples OFF
%endif

%bcond_with test
%if %{with test}
%global build_test ON
%else
%global build_test OFF
%endif

%bcond_with check

Summary:		Port of Facebook's LLaMA model in C/C++
Name:			llama-cpp
License:		MIT AND Apache-2.0 AND LicenseRef-Fedora-Public-Domain
Version:		b6948
Release:		1
URL:			https://github.com/ggml-org/llama.cpp
Source0:		https://github.com/ggml-org/llama.cpp/archive/%{version}/llama.cpp-%{version}.tar.gz

%ifarch %{x86_64}
%bcond_with rocm
%else
%bcond_with rocm
%endif

%if %{with rocm}
# Doesn't work yet
%global build_hip ON
%global toolchain rocm
# hipcc does not support some clang flags
%global build_cxxflags %(echo %{optflags} | sed -e 's/-fstack-protector-strong/-Xarch_host -fstack-protector-strong/' -e 's/-fcf-protection/-Xarch_host -fcf-protection/')
%else
%global build_hip OFF
%global toolchain gcc
%endif

BuildRequires:  xxd
BuildRequires:  cmake
BuildRequires:  curl
BuildRequires:  wget
#BuildRequires:  langpacks-en
# above are packages in .github/workflows/server.yml
BuildRequires:  pkgconfig(libcurl)
#BuildRequires:  gcc-c++
BuildRequires:  openmpi
#BuildRequires:  pthreadpool-devel
%if %{with examples}
BuildRequires:  python-devel
BuildRequires:  python3dist(pip)
BuildRequires:  python3dist(poetry)
%endif
# for blas backend
BuildRequires:  pkgconfig(openblas)
# for vulkan backend
BuildRequires:  pkgconfig(vulkan)
BuildRequires:  glslang-devel
BuildRequires:  glslang
BuildRequires:  pkgconfig(shaderc)
BuildRequires:  glslc
BuildRequires:	pkgconfig(OpenCL-Headers)
BuildRequires:	pkgconfig(OpenCL)
%if %{with rocm}
BuildRequires:	cmake(hip-lang)
BuildRequires:  hipblas-devel
BuildRequires:  rocm-comgr-devel
BuildRequires:  rocm-hip-devel
BuildRequires:  rocblas-devel
BuildRequires:  hipblas-devel
BuildRequires:  hipcc-libomp-devel
BuildRequires:  rocm-runtime-devel
BuildRequires:  rocm-rpm-macros
BuildRequires:  rocm-rpm-macros-modules

Requires:	   rocblas
Requires:	   hipblas
%endif

Requires:	   curl
Recommends:	 numactl

%global __requires_exclude cmake\\((hip|roc|mkl|intelsycl).*

%description
The main goal of llama.cpp is to run the LLaMA model using 4-bit
integer quantization on a MacBook

* Plain C/C++ implementation without dependencies
* Apple silicon first-class citizen - optimized via ARM NEON, Accelerate
  and Metal frameworks
* AVX, AVX2 and AVX512 support for x86 architectures
* Mixed F16 / F32 precision
* 2-bit, 3-bit, 4-bit, 5-bit, 6-bit and 8-bit integer quantization support
* CUDA, Metal and OpenCL GPU backend support

The original implementation of llama.cpp was hacked in an evening.
Since then, the project has improved significantly thanks to many
contributions. This project is mainly for educational purposes and
serves as the main playground for developing new features for the
ggml library.

%package devel
Summary:		Port of Facebook's LLaMA model in C/C++
Requires:	   %{name}%{?_isa} = %{version}-%{release}

%description devel
The main goal of llama.cpp is to run the LLaMA model using 4-bit
integer quantization on a MacBook

* Plain C/C++ implementation without dependencies
* Apple silicon first-class citizen - optimized via ARM NEON, Accelerate
  and Metal frameworks
* AVX, AVX2 and AVX512 support for x86 architectures
* Mixed F16 / F32 precision
* 2-bit, 3-bit, 4-bit, 5-bit, 6-bit and 8-bit integer quantization support
* CUDA, Metal and OpenCL GPU backend support

The original implementation of llama.cpp was hacked in an evening.
Since then, the project has improved significantly thanks to many
contributions. This project is mainly for educational purposes and
serves as the main playground for developing new features for the
ggml library.

%if %{with test}
%package test
Summary:		Tests for %{name}
Requires:	   %{name}%{?_isa} = %{version}-%{release}

%description test
%{summary}
%endif

%if %{with examples}
%package examples
Summary:		Examples for %{name}
Requires:	   %{name}%{?_isa} = %{version}-%{release}
Requires:	   python3dist(numpy)
#Requires:	   python3dist(torch)
Requires:	   python3dist(sentencepiece)

%description examples
%{summary}
%endif

%prep
%autosetup -p1 -n llama.cpp-%{version}

# verson the *.so
sed -i -e 's/POSITION_INDEPENDENT_CODE ON/POSITION_INDEPENDENT_CODE ON SOVERSION %{soversion}/' src/CMakeLists.txt
sed -i -e 's/POSITION_INDEPENDENT_CODE ON/POSITION_INDEPENDENT_CODE ON SOVERSION %{soversion}/' ggml/src/CMakeLists.txt

# Set a sane search path for the ggml backends
sed -i -e '/search_paths.push_back("\.\/")/a        search_paths.push_back("%{_libdir}/ggml-backends-%{soversion}")\;' ggml/src/ggml-backend-reg.cpp

# no android needed
rm -rf exmples/llma.android
# git cruft
find . -name '.gitignore' -exec rm -rf {} \;

%build
%if %{with examples}
cd %{_vpath_srcdir}/gguf-py
%py_build
cd -
%endif

%if %{with rocm}
module load rocm/default
%endif

export HIP_DEVICE_LIB_PATH=%{_libdir}/amdgcn/bitcode
# FIXME where is hipconfig.bin supposed to come from?
export HIP_USE_PERL_SCRIPTS=1

# FIXME add
#	-DGGML_HIP:BOOL=ON
# when we have the missing bits (hipblas and friends)
export CC=clang
export CXX=clang++
%cmake \
	-DCMAKE_INSTALL_LIBDIR=%{_lib} \
	-DCMAKE_SKIP_RPATH=ON \
	-DLLAMA_CURL:BOOL=ON \
	-DLLAMA_SERVER_SSL:BOOL=ON \
%ifarch znver1
	-DLLAMA_AVX:BOOL=ON \
	-DLLAMA_AVX2:BOOL=ON \
%else
	-DLLAMA_AVX:BOOL=OFF \
	-DLLAMA_AVX2:BOOL=OFF \
%endif
	-DLLAMA_AVX512=OFF \
	-DLLAMA_AVX512_VBMI=OFF \
	-DLLAMA_AVX512_VNNI=OFF \
	-DLLAMA_FMA=OFF \
	-DLLAMA_F16C=OFF \
	-DGGML_NATIVE:BOOL=OFF \
	-DGGML_VULKAN:BOOL=ON \
	-DGGML_CPU:BOOL=ON \
	-DGGML_CPU_ALL_VARIANTS:BOOL=ON \
	-DGGML_OPENCL:BOOL=ON \
	-DGGML_BLAS:BOOL=ON \
	-DGGML_BLAS_VENDOR=OpenBLAS \
	-DGGML_BACKEND_DL:BOOL=ON \
	-DCMAKE_HIP_COMPILER_ROCM_ROOT=%{_prefix} \
	-DGGML_LTO:BOOL=ON \
	-DGGML_BACKEND_DIR="%{backend_dir}" \
%ifarch %{aarch64}
	-DGGML_CPU_AARCH64:BOOL=ON \
%else
	-DGGML_CPU_AARCH64:BOOL=OFF \
	-DGGML_OPENCL_USE_ADRENO_KERNELS:BOOL=OFF \
%endif
%if %{with rocm}
	-DLLAMA_HIPBLAS=%{build_hip} \
	-DAMDGPU_TARGETS=${ROCM_GPUS} \
%endif
	-DLLAMA_BUILD_EXAMPLES=%{build_examples} \
	-DLLAMA_BUILD_TESTS=%{build_test}
	
%make_build

%if %{with rocm}
module purge
%endif


%install
%if %{with examples}
cd %{_vpath_srcdir}/gguf-py
%py_install
cd -
%endif

%make_install -C build

rm -rf %{buildroot}%{_libdir}/libggml_shared.*

%if %{with examples}
mkdir -p %{buildroot}%{_datarootdir}/%{name}
cp -r %{_vpath_srcdir}/examples %{buildroot}%{_datarootdir}/%{name}/
cp -r %{_vpath_srcdir}/models %{buildroot}%{_datarootdir}/%{name}/
cp -r %{_vpath_srcdir}/README.md %{buildroot}%{_datarootdir}/%{name}/
rm -rf %{buildroot}%{_datarootdir}/%{name}/examples/llama.android
%else
rm %{buildroot}%{_bindir}/convert*.py
%endif

mkdir -p %{buildroot}%{_libdir}/ggml-backends-%{soversion}
cp build/bin/*.so %{buildroot}%{_libdir}/ggml-backends-%{soversion}/

%if %{with test}
%if %{with check}
%check
%ctest
%endif
%endif

%files
%license LICENSE
%{_libdir}/libllama.so.%{soversion}
%{_libdir}/libggml.so.%{soversion}
%{_libdir}/libggml-base.so.%{soversion}
#{_bindir}/vulkan-shaders-gen
%dir %{_libdir}/ggml-backends-%{soversion}
%{_libdir}/ggml-backends-%{soversion}/*
%{_libdir}/ggml/libggml-*

%files devel
%dir %{_libdir}/cmake/llama
%doc README.md
%{_includedir}/ggml.h
%{_includedir}/ggml-*.h
%{_includedir}/llama.h
%{_includedir}/llama-cpp.h
%{_includedir}/gguf.h
%{_includedir}/mtmd-helper.h
%{_includedir}/mtmd.h
%{_libdir}/libllama.so
%{_libdir}/libggml.so
%{_libdir}/libggml-base.so
%{_libdir}/libmtmd.so
%{_libdir}/cmake/llama/*.cmake
%{_libdir}/cmake/ggml/ggml-config.cmake
%{_libdir}/cmake/ggml/ggml-version.cmake
%{_libdir}/pkgconfig/llama.pc

%if %{with test}
%files test
%{_bindir}/test-*
%endif

%if %{with examples}
%files examples
%{_bindir}/convert_hf_to_gguf.py
%{_bindir}/gguf-*
%{_bindir}/llama-*
%{_datarootdir}/%{name}/
%{python3_sitelib}/%{pypi_name}
%{python3_sitelib}/%{pypi_name}*.dist-info
#{python3_sitelib}/scripts
%endif
