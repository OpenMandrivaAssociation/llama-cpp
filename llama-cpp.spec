# For the extra python package gguf that comes with llama-cpp
%global pypi_name gguf
%define _disable_lto 1

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
Version:		b10107
Release:	6
%{!?rocm_llvm_maj_ver:%global rocm_llvm_maj_ver 23}
URL:			https://github.com/ggml-org/llama.cpp
Source0:		https://github.com/ggml-org/llama.cpp/archive/%{version}/llama.cpp-%{version}.tar.gz
# LLVM 23: amdgcn bf16 WMMA/MFMA builtins take short vectors, not __bf16
Patch0:		0001-llvm23-bf16-wmma-short-vectors.patch

# Backend DSO search path (also baked into libggml via GGML_BACKEND_DIR)
%global backend_dir %{_libdir}/ggml-backends-%{version}

# ROCm/HIP backend (TheRock 7.14 + gfx803 on OpenMandriva)
%ifarch %{x86_64}
%bcond_without rocm
%else
%bcond_with rocm
%endif

%if %{with rocm}
%global build_hip ON
# hip/clang: strip host-only -m* flags that break device compiles
%global build_cxxflags %(printf '%%s' '%{optflags}' | sed -E 's/-mfpmath=[^ ]+//g; s/ -m[a-z0-9+.=]+//g; s/-fstack-protector-strong/-Xarch_host -fstack-protector-strong/g; s/-fcf-protection[^ ]*//g')
%else
%global build_hip OFF
%global build_cxxflags %{optflags}
%endif

%ifarch x86_64
# Prefer -O3 over -Os for throughput-sensitive kernels
%global optflags %{optflags} -O3
%endif

BuildRequires:	cmake
BuildRequires:	ninja
BuildRequires:	git-core
BuildRequires:	xxd
BuildRequires:	pkgconfig(libcurl)
BuildRequires:	pkgconfig(openssl)
BuildRequires:	openmpi
%if %{with examples}
BuildRequires:	python-devel
BuildRequires:	python%{pyver}dist(build)
BuildRequires:	python%{pyver}dist(installer)
BuildRequires:	python%{pyver}dist(poetry-core)
BuildRequires:	python%{pyver}dist(wheel)
BuildRequires:	python%{pyver}dist(numpy)
BuildRequires:	python%{pyver}dist(pyyaml)
BuildRequires:	python%{pyver}dist(tqdm)
BuildRequires:	python%{pyver}dist(requests)
%endif
# for blas backend
BuildRequires:	pkgconfig(openblas)
# for vulkan backend
BuildRequires:	pkgconfig(vulkan)
BuildRequires:	glslang-devel
BuildRequires:	glslang
# ggml-vulkan find_package(SPIRV-Headers REQUIRED)
BuildRequires:	cmake(SPIRV-Headers)
BuildRequires:	pkgconfig(shaderc)
BuildRequires:	glslc
BuildRequires:	pkgconfig(OpenCL-Headers)
BuildRequires:	pkgconfig(OpenCL)
%if %{with rocm}
BuildRequires:	rocm-rpm-macros
BuildRequires:	hipcc
BuildRequires:	rocminfo
BuildRequires:	clang-tools
BuildRequires:	rocm-hip-devel
BuildRequires:	rocm-comgr-devel
BuildRequires:	rocm-runtime-devel
BuildRequires:	rocblas-devel
BuildRequires:	hipblas-devel
BuildRequires:	hipsolver-devel
BuildRequires:	clang >= %{rocm_llvm_maj_ver}

Requires:	rocblas
Requires:	hipblas
Requires:	hipsolver
Requires:	rocm-hip
%endif

Requires:	curl
Recommends:	numactl

# ggml-config.cmake lists optional backends (CUDA, DNNL, …) as hard deps — drop them
%global __requires_exclude cmake\\((hip|roc|mkl|intelsycl|cudatoolkit|CUDAToolkit|dnnl|DNNL|openvino|OpenVINO|sycl|SYCL).*

%description
llama.cpp runs large language models (GGUF) with optional CPU, Vulkan,
OpenCL, OpenBLAS and (on x86_64) AMD ROCm/HIP backends.

%package devel
Summary:	Development files for %{name}
Requires:	%{name}%{?_isa} = %{version}-%{release}
# Runtime backends are dlopen'd; keep devel light
Requires:	pkgconfig(openblas)

%description devel
Headers and CMake package for llama.cpp / ggml.

%if %{with test}
%package test
Summary:	Tests for %{name}
Requires:	%{name}%{?_isa} = %{version}-%{release}

%description test
%{summary}
%endif

%if %{with examples}
%package server
Summary:	OpenAI API compatible server for %{name}
Group:		Servers

%description server
OpenAI API compatible server for %{name}.

To test:
curl http://localhost:8080/v1/chat/completions -H "Content-Type: application/json" \
  -H "Authorization: Bearer OpenMandriva" \
  -d '{"model":"any","messages":[{"role":"user","content":"Hello"}]}'

%package examples
Summary:	CLI tools and examples for %{name}
Requires:	%{name}%{?_isa} = %{version}-%{release}
Requires:	python%{pyver}dist(numpy)
Recommends:	python%{pyver}dist(sentencepiece)

%description examples
CLI tools (llama-cli, llama-bench, quantize, …) and example scripts.
%endif

%prep
%autosetup -p1 -n llama.cpp-%{version}
# Patch0 applied by autosetup

# Prefer system model datadir when referenced relatively
if [ -f common/common.h ]; then
	sed -i -e 's,models/,%{_datadir}/models/,g' common/common.h || true
fi

# Drop android / VCS noise
rm -rf examples/llama.android 2>/dev/null || true
find . -name '.gitignore' -delete 2>/dev/null || true

%build
%if %{with examples}
if [ -d gguf-py ]; then
	cd gguf-py
	# PEP 517 wheel build (gguf-py uses poetry-core as build-backend)
	python3 -m build --wheel --no-isolation
	cd -
fi
%endif

export HIP_DEVICE_LIB_PATH=%{_libdir}/amdgcn/bitcode
export ROCM_PATH=%{_prefix}
export HIP_PATH=%{_prefix}
export CC=clang
%if %{with rocm}
# Prefer hipcc for ggml-hip (stable multi-arch fat binary). clang + enable_language(HIP)
# also works once rocm-hip-devel ships hip-lang (see /usr/lib64/cmake/hip-lang).
export CXX=hipcc
export CXXFLAGS="%{build_cxxflags}"
export CFLAGS="%{build_cxxflags}"
export LDFLAGS=$(printf '%s' "%{?__global_ldflags}" | sed -E 's/-mfpmath=[^ ]+//g; s/ -m[a-z0-9+.=]+//g')
%else
export CXX=clang++
%endif

# Arch-specific -D flags must be assembled in shell vars: %ifarch inside a
# backslash-continued %cmake block breaks the generated shell (OM %cmake).
%ifarch znver1
_ggml_isa_flags='-DGGML_AVX:BOOL=ON -DGGML_AVX2:BOOL=ON'
%else
_ggml_isa_flags='-DGGML_AVX:BOOL=OFF -DGGML_AVX2:BOOL=OFF'
%endif
_ggml_isa_flags="$_ggml_isa_flags -DGGML_AVX512:BOOL=OFF -DGGML_FMA:BOOL=OFF -DGGML_F16C:BOOL=OFF"
%ifarch %{aarch64}
_ggml_arch_flags='-DGGML_CPU_AARCH64:BOOL=ON'
%else
_ggml_arch_flags='-DGGML_CPU_AARCH64:BOOL=OFF -DGGML_OPENCL_USE_ADRENO_KERNELS:BOOL=OFF'
%endif
%if %{with rocm}
# GPU lists use ';'; keep them inside double quotes at assignment time so the
# shell does not treat ';' as a command separator.
_ggml_hip_flags="-DCMAKE_CXX_COMPILER=hipcc -DGGML_HIP:BOOL=ON -DGGML_HIP_GRAPHS:BOOL=OFF -DGGML_HIP_RCCL:BOOL=OFF -DGPU_TARGETS=%{rocm_gpu_targets} -DAMDGPU_TARGETS=%{rocm_gpu_targets} -DCMAKE_PREFIX_PATH=%{_prefix}"
%else
_ggml_hip_flags=
%endif

%cmake \
	-G Ninja \
	-DCMAKE_BUILD_TYPE=Release \
	-DCMAKE_INSTALL_LIBDIR=%{_lib} \
	-DCMAKE_SKIP_RPATH=ON \
	-DBUILD_SHARED_LIBS=ON \
	-DGGML_NATIVE:BOOL=OFF \
	-DGGML_LTO:BOOL=OFF \
	-DGGML_BACKEND_DL:BOOL=ON \
	-DGGML_BACKEND_DIR="%{backend_dir}" \
	-DGGML_CPU:BOOL=ON \
	-DGGML_CPU_ALL_VARIANTS:BOOL=ON \
	-DGGML_VULKAN:BOOL=ON \
	-DGGML_OPENCL:BOOL=ON \
	-DGGML_BLAS:BOOL=ON \
	-DGGML_BLAS_VENDOR=OpenBLAS \
	$_ggml_isa_flags \
	$_ggml_arch_flags \
	$_ggml_hip_flags \
	-DLLAMA_OPENSSL:BOOL=ON \
	-DLLAMA_BUILD_COMMON:BOOL=ON \
	-DLLAMA_BUILD_TOOLS:BOOL=ON \
	-DLLAMA_BUILD_SERVER:BOOL=ON \
	-DLLAMA_BUILD_EXAMPLES=%{build_examples} \
	-DLLAMA_BUILD_TESTS=%{build_test} \
	-DLLAMA_BUILD_UI:BOOL=ON \
	-DLLAMA_TOOLS_INSTALL:BOOL=ON

# The cmake macro already chdirs into the build/ subdirectory
%ninja_build

%install
# %install is a fresh shell; cmake wrote Ninja files under build/
%if %{with examples}
if [ -d gguf-py ]; then
	python3 -m installer --destdir=%{buildroot} gguf-py/dist/*.whl
fi
%endif

cd build
DESTDIR=%{buildroot} /usr/bin/ninja install -j%{?_smp_build_ncpus}%{!?_smp_build_ncpus:16}
cd ..

# Drop unversioned shared leftovers if any
rm -f %{buildroot}%{_libdir}/libggml_shared.* 2>/dev/null || true

# Backend plugins land in %{backend_dir} via GGML_BACKEND_DIR; drop accidental
# copies of the main base library (duplicate of %{_libdir}/libggml-base.so.*)
mkdir -p %{buildroot}%{backend_dir}
rm -f %{buildroot}%{backend_dir}/libggml-base.so* \
	%{buildroot}%{backend_dir}/libggml.so* 2>/dev/null || true

%if %{with examples}
mkdir -p %{buildroot}%{_unitdir} %{buildroot}%{_sysconfdir}/sysconfig
cat >%{buildroot}%{_unitdir}/llama.service <<'UNIT'
[Unit]
Description=OpenAI API compatible AI server (llama.cpp)

[Service]
EnvironmentFile=-%{_sysconfdir}/sysconfig/llama-server
ExecStart=bash -c "exec %{_bindir}/llama-server $${MODEL:+--model $${MODEL}} $${HOST:+--host $${HOST}} $${PORT:+--port $${PORT}} $${API_KEY:+--api_key $${API_KEY}} $${LLAMA_OPTIONS}"
KillMode=process
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
UNIT

cat >%{buildroot}%{_sysconfdir}/sysconfig/llama-server <<'CFG'
# Point this at a GGUF model (https://huggingface.co/models?library=gguf)
#MODEL=/srv/ai/model.gguf
#API_KEY=OpenMandriva
HOST=127.0.0.1
PORT=8080
# GPU offload: -1 = all layers. HIP devices: HIP_VISIBLE_DEVICES=0
LLAMA_OPTIONS="--n-gpu-layers -1"
CFG

mkdir -p %{buildroot}%{_datarootdir}/%{name}
cp -a examples %{buildroot}%{_datarootdir}/%{name}/ 2>/dev/null || true
cp -a models %{buildroot}%{_datarootdir}/%{name}/ 2>/dev/null || true
cp -a README.md %{buildroot}%{_datarootdir}/%{name}/ 2>/dev/null || true
rm -rf %{buildroot}%{_datarootdir}/%{name}/examples/llama.android 2>/dev/null || true
%endif

%if %{with test}
%if %{with check}
%check
cd build && ctest --output-on-failure || true
%endif
%endif

%files
%license LICENSE
%{_libdir}/libggml.so.*
%{_libdir}/libggml-base.so.*
%{_libdir}/libllama.so.*
%{_libdir}/libllama-common.so.*
%{_libdir}/libmtmd.so.*
%dir %{backend_dir}
%{backend_dir}/*

%files devel
%doc README.md
%{_includedir}/ggml.h
%{_includedir}/ggml-*.h
%{_includedir}/llama.h
%{_includedir}/llama-cpp.h
%{_includedir}/gguf.h
%{_includedir}/mtmd*.h
%{_libdir}/libllama.so
%{_libdir}/libllama-common.so
%{_libdir}/libggml.so
%{_libdir}/libggml-base.so
%{_libdir}/libmtmd.so
%{_libdir}/cmake/llama/
%{_libdir}/cmake/ggml/
%{_libdir}/pkgconfig/llama.pc

%if %{with test}
%files test
%{_bindir}/test-*
%endif

%if %{with examples}
%files server
%{_bindir}/llama-server
%{_libdir}/libllama-server-impl.so*
%{_unitdir}/llama.service
%config(noreplace) %{_sysconfdir}/sysconfig/llama-server

%files examples
%{_bindir}/llama
%{_bindir}/llama-*
%exclude %{_bindir}/llama-server
%{_bindir}/gguf-*
# private tool helpers (unversioned SONAMEs)
%{_libdir}/libllama-*-impl.so*
%exclude %{_libdir}/libllama-server-impl.so*
%{_datarootdir}/%{name}/
# convert scripts / gguf-py if present
%{python3_sitelib}/%{pypi_name}
%{python3_sitelib}/%{pypi_name}*.dist-info
%endif
