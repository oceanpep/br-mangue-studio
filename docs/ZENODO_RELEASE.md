# Zenodo release checklist

Zenodo should archive a versioned source-and-binary release after the CMMA
benchmark and the second-computer smoke test are complete.

1. Select and add an OSI-approved software license to the repository.
2. Confirm the release version (`1.0.0`), authors, affiliation, abstract and
   citation metadata in `CITATION.cff`.
3. Commit the source, documentation, tests and the validated Windows
   executable. Do not include local rasters, `results/` folders or private
   absolute paths.
4. Create the Git tag `v1.0.0` and a GitHub Release with the executable,
   checksums and a short list of changes.
5. Enable the repository in Zenodo and select the GitHub Release for archival.
6. Check the archived record before publication: title, creators, version,
   license, files and README link.
7. Add the DOI badge and DOI link to the README, website and manuscript only
   after Zenodo has minted the record.

The Zenodo DOI identifies the archived software release. It is separate from
the DOI that will later identify the journal article.

