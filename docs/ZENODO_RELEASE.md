# Zenodo release archive

BR-MANGUE Studio uses the GitHub–Zenodo integration. The repository must be enabled at https://zenodo.org/account/settings/github/ before publishing a release. An active release webhook was verified for version 1.4.0 preparation.

1. Update `pyproject.toml`, `APP_VERSION`, `CITATION.cff`, `.zenodo.json`, and the changelog with the same version.
2. Run the automated tests and packaged smoke checks on Linux and Windows; retain the full-CMMA software-test report separately from ecological validation.
3. Merge the reviewed changes, tag the tested commit, and publish a GitHub release with both executables and SHA-256 checksums.
4. Verify that Zenodo created a public record with the correct version, MIT license, and four creators in the order specified by `.zenodo.json`. Do not create a separate independent deposit for every update.
5. Record the version DOI for exact reproduction and the concept DOI for the software across versions. Link the confirmed concept DOI from the site and citation metadata.

The automatic archive preserves the tagged source ZIP; executable assets remain linked from GitHub. Zenodo gives `.zenodo.json` priority over `CITATION.cff`; keep both consistent.

Official instructions: https://help.zenodo.org/docs/github/describe-software/zenodo-json/

## Verified public archive — 20 October 2026

- Version 1.4.0: https://doi.org/10.5281/zenodo.23509309
- All versions (concept DOI): https://doi.org/10.5281/zenodo.23509308
- Public record: https://zenodo.org/records/23509309
- Tagged source: `v1.4.0`, commit `29c602afeb0e2c6e479d1a90306f5d226b057645`.

The automatic deposit was checked for version, the four creators and their
UFMA affiliations, MIT license, and the source ZIP. Windows/Linux binaries
and their SHA-256 checksums are on the matching GitHub release. The DOI was
added to citation documentation after archiving; the tag was not changed.
For a future release, update the version DOI only after its new record exists.
