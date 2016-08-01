from debian import deb822
import re
import gzip
import lzma
import tarfile
import subprocess
import hashlib

pkgver_base = "16.30.3"
pkgver_build = "306809"
pkgrel = 4

pkgver = "{0}.{1}".format(pkgver_base, pkgver_build)
url_ref="http://support.amd.com/en-us/kb-articles/Pages/AMDGPU-PRO-Beta-Driver-for-Vulkan-Release-Notes.aspx"
dlagents="https::/usr/bin/wget --referer {0} -N %u".format(url_ref)

source_url = "https://www2.ati.com/drivers/linux/amdgpu-pro_{0}-{1}.tar.xz".format(pkgver_base, pkgver_build)

subprocess.run(["/usr/bin/wget", "--referer", url_ref, "-N", source_url])
source_file = "amdgpu-pro_{0}-{1}.tar.xz".format(pkgver_base, pkgver_build)

block = 64 * 1024
hash = hashlib.sha256()
with open(source_file, 'rb') as f:
	buf = f.read(block)
	while len(buf) > 0:
		hash.update(buf)
		buf = f.read(block)
source_digest = hash.hexdigest()

header_tpl = """# Author: Janusz Lewandowski <lew21@xtreeme.org>
# Maintainer: David McFarland <corngood@gmail.com>
# Autogenerated from AMD's Packages file

pkgbase=amdgpu-pro-installer
pkgname={package_names}
if [ "$ALL_PACKAGES" = "true" ]; then
	pkgname+={optional_names}
fi
pkgver={pkgver}
pkgrel={pkgrel}
arch=('x86_64')
url='http://www.amd.com'
license=('custom:AMD')
makedepends=('wget')

DLAGENTS='{dlagents}'

source=('{source_url}')
sha256sums=('{source_digest}')
"""

package_header_tpl = """
package_{NAME} () {{
	pkgdesc={DESC}
	depends={DEPENDS}
	arch=('{ARCH}')

	rm -Rf "${{srcdir}}"/{Package}_{Version}_{Architecture}
	mkdir "${{srcdir}}"/{Package}_{Version}_{Architecture}
	cd "${{srcdir}}"/{Package}_{Version}_{Architecture}
	ar x "${{srcdir}}"/amdgpu-pro-driver/{Filename}
	tar -C "${{pkgdir}}" -xf data.tar.xz
"""

package_footer = """}
"""

special_ops = {
	"amdgpu-pro-graphics": """
	provides=('libgl')
	conflicts=('libgl')
""",
	"amdgpu-pro-lib32": """
	provides=('lib32-libgl')
	conflicts=('lib32-libgl')
""",
	"amdgpu-pro-core": """
	mv ${pkgdir}/lib ${pkgdir}/usr/
	mkdir -p ${pkgdir}/etc/ld.so.conf.d/
	ln -s /usr/lib/amdgpu-pro/ld.conf ${pkgdir}/etc/ld.so.conf.d/10-amdgpu-pro.conf
	mkdir -p ${pkgdir}/etc/modprobe.d/
	ln -s /usr/lib/amdgpu-pro/modprobe.conf ${pkgdir}/etc/modprobe.d/amdgpu-pro.conf
	install=amdgpu-pro-core.install
""",
	"amdgpu-pro-firmware": """
	mv ${pkgdir}/lib ${pkgdir}/usr/
""",
	"xserver-xorg-video-amdgpu-pro": "\tln -sfn 1.18 ${pkgdir}/usr/lib/x86_64-linux-gnu/amdgpu-pro/xorg",
}

replace_deps = {
	"libc6": None,
	"libgcc1": None,
	"libstdc++6": None,
	"libx11-6": "libx11",
	"libx11-xcb1": None,
	"libxcb-dri2-0": "libxcb",
	"libxcb-dri3-0": "libxcb",
	"libxcb-present0": "libxcb",
	"libxcb-sync1": "libxcb",
	"libxcb-glx0": "libxcb",
	"libxcb1": "libxcb",
	"libxext6": "libxext",
	"libxshmfence1": "libxshmfence",
	"libxdamage1": "libxdamage",
	"libxfixes3": "libxfixes",
	"libxxf86vm1": "libxxf86vm",
	"libudev1": "libsystemd",
	"libpciaccess0": "libpciaccess",
	"libepoxy0": "libepoxy",
	"libelf1": None, # no lib32- package in Arch, just disabling for now
	"xserver-xorg-core": "xorg-server",
	"libcunit1": "cunit",
	"libdrm-radeon1": "libdrm",
	"amdgpu-pro-firmware": "linux-firmware",
	"libssl1.0.0": "openssl",
	"zlib1g": "zlib",
}

dependency = re.compile(r"([^ ]+)(?: \((.+)\))?")

arch_map = {
	"amd64": "x86_64",
	"i386": "i686",
	"all": "any"
}

optional_packages = frozenset([
	"amdgpu-pro-firmware",
	"amdgpu-pro-dkms"
])

deb_archs={}

def quote(string):
	return "\"" + string.replace("\\", "\\\\").replace("\"", "\\\"") + "\""

def convertName(name, info):
	if info["Architecture"] == "i386" and (name not in deb_archs or "any" not in deb_archs[name]):
		return "lib32-" + name
	return name

def convertVersionSpecifier(name, spec, names):
	if name == "linux-firmware":
		return ""
	if name in names:
		return "=" + pkgver + "-" + str(pkgrel)
	if not spec:
		return ""

	sign, spec = spec.split(" ", 1)

	spec = spec.strip()
	if ":" in spec:
		whatever, spec = spec.rsplit(":", 1)
	return sign + spec

def convertPackage(info, names):
	if info["Architecture"] == "i386":
		name = "lib32-" + info["Package"]
		arch = "x86_64"
	else:
		name = info["Package"]
		arch = arch_map[info["Architecture"]]

	try:
		deps = info["Depends"].split(", ")
	except:
		deps = []

	deps = [dependency.match(dep).groups() for dep in deps]
	deps = [(replace_deps[name] if name in replace_deps else name, version) for name, version in deps]
	deps = ["'" + convertName(name, info) + convertVersionSpecifier(name, version, names) + "'" for name, version in deps if name]
	deps2 = []
	for dep in deps:
		if not dep in deps2:
			deps2.append(dep)
	deps = "(" + " ".join(deps2) + ")"

	special_op = special_ops[info["Package"]] if info["Package"] in special_ops else ""

	desc = info["Description"].split("\n")
	if len(desc) > 2:
		desc = desc[0]
	else:
		desc = " ".join(x.strip() for x in desc)

	ret = package_header_tpl.format(DEPENDS=deps, NAME=name, ARCH=arch, DESC=quote(desc), **info)
	if special_op:
		ret += special_op + "\n"
	if info["Architecture"] == "i386":
		ret += "\trm -Rf ${pkgdir}/usr/share/doc ${pkgdir}/usr/include\n"
	ret += package_footer

	return ret

def writePackages(f):
	package_list=[]
	package_names=[]
	optional_names=[]

	for info in deb822.Packages.iter_paragraphs(f):
		if not info["Package"] in deb_archs:
			deb_archs[info["Package"]] = set()

		deb_archs[info["Package"]].add(info["Architecture"])

		name = "lib32-" + info["Package"] if info["Architecture"] == "i386" else info["Package"]

		if info["Package"] in optional_packages:
			optional_names.append(name)
		else:
			package_names.append(name)

		package_list.append(info)

	names = ["lib32-" + info["Package"] if info["Architecture"] == "i386" else info["Package"] for info in package_list]

	print(header_tpl.format(package_names="(" + " ".join(package_names) + ")",
				optional_names="(" + " ".join(optional_names) + ")",
				pkgver=pkgver, pkgrel=pkgrel,
				dlagents=dlagents, source_url=source_url, source_digest=source_digest))

	f.seek(0)

	for info in package_list:
		print(convertPackage(info, package_names + optional_names))

with lzma.open(source_file, "r") as tar:
	with tarfile.open(fileobj=tar) as tf:
		with tf.extractfile("amdgpu-pro-driver/Packages.gz") as gz:
			with gzip.open(gz, "r") as packages:
				writePackages(packages)
