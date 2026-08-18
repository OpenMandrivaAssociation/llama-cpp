# llama.cpp on the system ggml package (libggml + dlopen backends).
# Do not compile bundled ggml: backends (CPU ISA variants, Vulkan, OpenCL,
# HIP/ROCm) live in ggml / ggml-backend-*.

%global pypi_name gguf

# Out-of-tree cmake/ninja can leave empty debugsourcefiles.list; rpm then
# fails on x86_64/aarch64. Keep -debuginfo; skip empty -debugsource.
%undefine _debugsource_packages

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

Summary:		LLM inference in C/C++ (llama.cpp)
Name:			llama-cpp
Version:		b10453
Release:		3
License:		MIT AND Apache-2.0 AND LicenseRef-Fedora-Public-Domain
Group:			Sciences/Other
URL:			https://github.com/ggml-org/llama.cpp
Source0:		https://github.com/ggml-org/llama.cpp/archive/%{version}/llama.cpp-%{version}.tar.gz

# Prefer -O3 over distro -Os for the inference hot path
%global optflags %{optflags} -O3

BuildRequires:	pkgconfig(libcurl)
BuildRequires:	pkgconfig(openssl)
BuildRequires:	cmake(ggml) >= 0.20.0
BuildRequires:	git-core
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

Requires:	curl
Requires:	%{mklibname ggml}%{?_isa} >= 0.20.0
Recommends:	numactl
# Runtime backends are dlopen'd from ggml; recommend the useful ones.
Recommends:	ggml-backend-blas%{?_isa}
Recommends:	ggml-backend-vulkan%{?_isa}
Suggests:	ggml-backend-opencl%{?_isa}
Suggests:	ggml-backend-hip%{?_isa}

# ggml-config.cmake lists optional backends (CUDA, DNNL, …) as hard deps
%global __requires_exclude cmake\\((hip|roc|mkl|intelsycl|cudatoolkit|CUDAToolkit|dnnl|DNNL|openvino|OpenVINO|sycl|SYCL).*

BuildSystem:	cmake
BuildOption:	-DCMAKE_C_COMPILER=clang
BuildOption:	-DCMAKE_CXX_COMPILER=clang++
BuildOption:	-DBUILD_SHARED_LIBS:BOOL=ON
BuildOption:	-DLLAMA_USE_SYSTEM_GGML:BOOL=ON
BuildOption:	-DLLAMA_OPENSSL:BOOL=ON
BuildOption:	-DLLAMA_BUILD_COMMON:BOOL=ON
BuildOption:	-DLLAMA_BUILD_TOOLS:BOOL=ON
BuildOption:	-DLLAMA_BUILD_SERVER:BOOL=ON
BuildOption:	-DLLAMA_BUILD_APP:BOOL=ON
BuildOption:	-DLLAMA_BUILD_EXAMPLES=%{build_examples}
BuildOption:	-DLLAMA_BUILD_TESTS=%{build_test}
# Source-tree UI only — prebuilt tarball is fetched from Hugging Face
# and ABF builders have no network.
BuildOption:	-DLLAMA_BUILD_UI:BOOL=ON
BuildOption:	-DLLAMA_USE_PREBUILT_UI:BOOL=OFF
BuildOption:	-DLLAMA_TOOLS_INSTALL:BOOL=ON

# 0002: llama-export-lora used ggml_backend_cpu_init() which is not in
#       libggml when backends are dlopen'd. Load CPU via the registry.
# Keep after all preamble tags: %patchlist is a section-like directive.
%patchlist
0002-export-lora-system-ggml.patch

%description
llama.cpp runs GGUF language (and vision) models. Tensor kernels come
from the system ggml package; optional accelerators are separate:

* ggml-backend-blas — OpenBLAS
* ggml-backend-vulkan — Vulkan
* ggml-backend-opencl — OpenCL
* ggml-backend-hip — AMD ROCm/HIP

%package devel
Summary:	Development files for %{name}
Group:		Development/C++
Requires:	%{name}%{?_isa} = %{EVRD}
Requires:	cmake(ggml)

%description devel
Headers, pkg-config and CMake package config for llama.cpp.
Requires system ggml (cmake(ggml)).

%if %{with test}
%package test
Summary:	Tests for %{name}
Group:		Development/Other
Requires:	%{name}%{?_isa} = %{EVRD}

%description test
%{summary}
%endif

%if %{with examples}
%package server
Summary:	OpenAI API compatible server for %{name}
Group:		Servers
Requires:	%{name}%{?_isa} = %{EVRD}

%description server
OpenAI API compatible server for %{name}.

Config: %{_sysconfdir}/sysconfig/llama-server

To test:
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer OpenMandriva" \
  -d '{"model":"any","messages":[{"role":"user","content":"Hello"}]}'

%package examples
Summary:	CLI tools and examples for %{name}
Group:		Sciences/Other
Requires:	%{name}%{?_isa} = %{EVRD}
Requires:	python%{pyver}dist(numpy)
Requires:	python%{pyver}dist(torch)
Requires:	python%{pyver}dist(transformers)
Requires:	python%{pyver}dist(safetensors)
Recommends:	python%{pyver}dist(sentencepiece)
Recommends:	python%{pyver}dist(huggingface-hub)

%description examples
CLI tools (llama, llama-cli, llama-bench, llama-quantize,
llama-export-lora, llama-convert-lora-to-gguf, …) and example scripts.

Convert a Hugging Face PEFT adapter to GGUF:
  llama-convert-lora-to-gguf --base /path/to/hf-base --outtype f16 \
    --outfile adapter.gguf /path/to/adapter

Merge a GGUF LoRA into a base GGUF:
  llama-export-lora -m base.gguf --lora adapter.gguf -o merged-f16.gguf
%endif

%prep
%autosetup -p1 -n llama.cpp-%{version}

rm -rf examples/llama.android 2>/dev/null || true
find . -name '.gitignore' -delete 2>/dev/null || true

%if %{with examples}
%build -p
if [ -d gguf-py ]; then
	cd gguf-py
	python -m build --wheel --no-isolation
	cd -
fi
%endif

%if %{with examples}
%install -a
python -m installer --destdir=%{buildroot} gguf-py/dist/*.whl

mkdir -p %{buildroot}%{_unitdir} %{buildroot}%{_sysconfdir}/sysconfig
cat >%{buildroot}%{_unitdir}/llama.service <<'UNIT'
[Unit]
Description=OpenAI API compatible AI server (llama.cpp)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=-%{_sysconfdir}/sysconfig/llama-server
ExecStart=bash -c "exec %{_bindir}/llama-server $${MODEL:+--model $${MODEL}} $${HOST:+--host $${HOST}} $${PORT:+--port $${PORT}} $${API_KEY:+--api_key $${API_KEY}} $${LLAMA_OPTIONS}"
KillMode=process
Restart=on-failure
RestartSec=5s

# Unprivileged, no extra caps. Model file must be readable by this user
# (e.g. mode 0644 under /srv/ai — /home is hidden, see ProtectHome).
DynamicUser=yes
SupplementaryGroups=render video
UMask=0077
NoNewPrivileges=yes
CapabilityBoundingSet=
AmbientCapabilities=
RestrictSUIDSGID=yes
RestrictRealtime=yes
LockPersonality=yes
ProtectHostname=yes
ProtectClock=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectKernelLogs=yes
ProtectControlGroups=yes
ProtectProc=invisible
RestrictNamespaces=yes
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6 AF_NETLINK
SystemCallArchitectures=native
RemoveIPC=yes

# /usr /boot /etc read-only; /home /root invisible. Private /tmp.
# Models: /srv/ai is visible read-only ("-" = skip if missing).
# Extra trees: drop-in  ReadOnlyPaths=-/other/models
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
PrivateUsers=no
ReadOnlyPaths=-/srv/ai
# Mesa/Vulkan shader cache, HIP dumps
CacheDirectory=llama-server
Environment=XDG_CACHE_HOME=%{_localstatedir}/cache/llama-server

# GPU: DRM render node + KFD (ROCm). No MemoryDenyWriteExecute —
# Vulkan/HIP compile executable code.
DevicePolicy=closed
DeviceAllow=/dev/null rw
DeviceAllow=/dev/zero rw
DeviceAllow=/dev/urandom r
DeviceAllow=/dev/random r
DeviceAllow=char-drm rw
DeviceAllow=/dev/dri rw
DeviceAllow=/dev/kfd rw

[Install]
WantedBy=multi-user.target
UNIT

cat >%{buildroot}%{_sysconfdir}/sysconfig/llama-server <<'CFG'
# Point this at a GGUF model (https://huggingface.co/models?library=gguf).
# The systemd unit hides /home and /root (ProtectHome=yes) and only
# allows reading models from /srv/ai (ReadOnlyPaths=-/srv/ai; "-"
# means the unit still starts if that directory is absent). Make the
# file readable by the service (e.g. chmod 0644). Extra trees: drop-in
#   ReadOnlyPaths=-/other/models
#MODEL=/srv/ai/model.gguf
# API_KEY is passed as --api-key. Clients must send
#   Authorization: Bearer <API_KEY>
# Unset = no auth (anyone who can reach HOST:PORT can use the server).
#API_KEY=OpenMandriva
HOST=127.0.0.1
PORT=8080
# GPU offload: --n-gpu-layers -1 = all layers.
# List backends/devices:  llama-server --list-devices
#   (Vulkan0, ROCm0, …). Pick one with --device, e.g. Vulkan:
# LLAMA_OPTIONS="--n-gpu-layers -1 --device Vulkan0"
# HIP/ROCm device index: HIP_VISIBLE_DEVICES=0
# Some GGUFs still embed SwissAI's original Apertus Jinja. llama.cpp's
# auto-parser cannot compile that (fatal at load). Use the adapted
# template llama.cpp already ships:
#   --jinja --chat-template-file /usr/share/llama-cpp/models/templates/Apertus-8B-Instruct.jinja
LLAMA_OPTIONS="--n-gpu-layers -1"
CFG

mkdir -p %{buildroot}%{_datarootdir}/%{name}
cp -a models %{buildroot}%{_datarootdir}/%{name}/ 2>/dev/null || true
cp -a README.md %{buildroot}%{_datarootdir}/%{name}/ 2>/dev/null || true
# Hugging Face → GGUF converters. They import the sibling conversion/
# package (and system gguf-py). Keep them next to each other.
if [ -f convert_lora_to_gguf.py ]; then
	cp -a convert_lora_to_gguf.py convert_hf_to_gguf.py \
		%{buildroot}%{_datarootdir}/%{name}/
	cp -a conversion %{buildroot}%{_datarootdir}/%{name}/
	find %{buildroot}%{_datarootdir}/%{name}/conversion -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
	cat > %{buildroot}%{_bindir}/llama-convert-lora-to-gguf <<EOF
#!/bin/sh
# system gguf-py is already on PYTHONPATH
export NO_LOCAL_GGUF=1
exec /usr/bin/python %{_datarootdir}/%{name}/convert_lora_to_gguf.py "\$@"
EOF
	cat > %{buildroot}%{_bindir}/llama-convert-hf-to-gguf <<EOF
#!/bin/sh
export NO_LOCAL_GGUF=1
exec /usr/bin/python %{_datarootdir}/%{name}/convert_hf_to_gguf.py "\$@"
EOF
	chmod 755 %{buildroot}%{_bindir}/llama-convert-lora-to-gguf \
		%{buildroot}%{_bindir}/llama-convert-hf-to-gguf
fi
# Do not ship the examples/ source tree: env shebangs trip rpmlint
# (env-script-interpreter) and the compiled tools already live in bindir.
# gguf-py console scripts: /usr/bin/env python3 → /usr/bin/python
find %{buildroot}%{python3_sitelib}/%{pypi_name} %{buildroot}%{_bindir} \
		%{buildroot}%{_datarootdir}/%{name} \
	-type f \( -name '*.py' -o -perm /111 \) -print0 2>/dev/null \
	| xargs -0 -r sed -i \
		-e '1s|^#!/usr/bin/env python3|#!/usr/bin/python|' \
		-e '1s|^#!/usr/bin/env python|#!/usr/bin/python|'
%endif

%if %{with test}
%if %{with check}
%check
cd _OMV_rpm_build && ctest --output-on-failure || true
%endif
%endif

%files
%license LICENSE
%{_libdir}/libllama.so.*
%{_libdir}/libllama-common.so.*
%{_libdir}/libmtmd.so.*

%files devel
%doc README.md
%{_includedir}/llama.h
%{_includedir}/llama-cpp.h
%{_includedir}/mtmd*.h
%{_libdir}/libllama.so
%{_libdir}/libllama-common.so
%{_libdir}/libmtmd.so
%{_libdir}/cmake/llama/
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
%{python3_sitelib}/%{pypi_name}
%{python3_sitelib}/%{pypi_name}*.dist-info
%endif
