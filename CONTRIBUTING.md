# Contributing to BR-MANGUE Studio

BR-MANGUE Studio is research software. Contributions should therefore be
small, reviewable, documented, and reproducible on a clean checkout.

Before opening a pull request:

1. describe the problem and the intended behavior;
2. add or update tests for changed behavior;
3. run `python -m pytest tests -q`;
4. document changes to outputs, model rules, or performance measurements;
5. avoid committing rasters, generated animations, private data, or local
   build directories.

Changes to model rules require an explicit explanation of compatibility with
the reference implementation and a before/after comparison on a fixed input.
Performance claims should include the hardware, input dimensions, engine,
block size, number of repetitions, and the `metadata.json` produced by the
run.
