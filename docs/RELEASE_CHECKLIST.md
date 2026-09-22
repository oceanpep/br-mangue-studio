# Public release checklist

Use this checklist before creating a citable BR-MANGUE Studio release.

## Repository

- [ ] Choose and add an OSI-approved open-source license.
- [ ] Confirm that `pyproject.toml`, the executable splash screen, the website,
      and `CITATION.cff` use the same public version.
- [ ] Update the changelog and describe compatibility with earlier runs.
- [ ] Run the full test suite on a clean environment.
- [ ] Build the Windows executable from the tagged source commit.
- [ ] Test the executable on a second Windows computer.
- [ ] Confirm that a new project runs without the developer's local paths.

## Scientific evidence

- [ ] Preserve a benchmark input manifest with SHA-256 hashes.
- [ ] Run continuous and block engines with identical parameters.
- [ ] Compare annual trajectories and final rasters cell by cell.
- [ ] Record `metadata.json`, `trajectory.csv`, and the output manifest for
      every benchmark repetition.
- [ ] Keep ecological validation claims separate from performance claims.

## DOI and article materials

- [ ] Create the GitHub release only after the source and executable are final.
- [ ] Enable the repository in Zenodo and archive the tagged release.
- [ ] Add the Zenodo DOI to the website, README, and article manuscript.
- [ ] Preserve the exact executable checksum and source commit in the Zenodo
      record.
