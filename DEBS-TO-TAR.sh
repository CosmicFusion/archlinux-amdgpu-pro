
#!bin/bash

# A script that takes the DEBS "GET-DEBS.sh" downloaded and throws them into a tar file pkgbuild could understand .

. ./versions

### make tar.xz ###

tar -cf - amdgpu-pro-$pkgver_base-$pkgver_build-ubuntu-$ubuntu_ver | xz -9zve -T0 >amdgpu-pro-archive.tar.xz
