# Third-Party Notices

StateWake is distributed under the Apache License 2.0. This document records the licenses of the runtime dependencies declared by StateWake and the relevant transitive runtime dependencies resolved by the release lockfile.

StateWake does **not** vendor the source code of these Python dependencies into its own source distribution or wheel. They are installed separately by the package installer according to the dependency metadata.

## Direct runtime dependencies

| Dependency | Version | License | Source |
| --- | --- | --- | --- |
| PyNaCl | 1.6.2 | Apache-2.0 | https://pypi.org/project/PyNaCl/1.6.2/ |
| opentelemetry-api | 1.44.0 | Apache-2.0 | https://pypi.org/project/opentelemetry-api/1.44.0/ |
| filelock | 3.32.4 | MIT | https://pypi.org/project/filelock/3.32.4/ |

## Transitive runtime dependencies

The release lockfile resolves the following runtime dependencies for the direct dependencies above:

| Dependency | Version | License | Required by |
| --- | --- | --- | --- |
| cffi | 2.0.0 | MIT | PyNaCl |
| pycparser | 3.0 | BSD-3-Clause | cffi |
| typing-extensions | 4.16.0 | PSF-2.0 | opentelemetry-api |

## Bundled native dependency used by PyNaCl

PyNaCl 1.6.2 bundles libsodium in its distribution. PyNaCl's release metadata identifies its own license as Apache-2.0 and includes a separate libsodium license file. PyNaCl 1.6.2 updates its bundled libsodium to the 1.0.20 stable line.

| Component | License | Source |
| --- | --- | --- |
| libsodium | ISC | https://github.com/jedisct1/libsodium/blob/master/LICENSE |

This notice does not replace the license files distributed by the respective dependency projects.

## Compatibility assessment

The runtime dependency set contains permissive/open-source licenses: Apache-2.0, MIT, BSD-3-Clause, PSF-2.0, and ISC. No runtime dependency identified in the current StateWake v0.1.0 lockfile introduces a copyleft license requirement that would require StateWake to change its Apache-2.0 licensing model.

License information was checked against the dependency projects' published package/repository metadata on 2026-09-15. Dependency versions and license terms can change in future releases; update this inventory whenever runtime dependency versions change.
