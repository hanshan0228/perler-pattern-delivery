# Continuous validation for Perler Pattern Delivery

Every push to `main`, pull request, and manual workflow dispatch runs the committed test suite in GitHub Actions using Python 3.11, 3.12 and 3.13. This is regression coverage, **not** a guarantee of customer portrait beauty or physical bead color calibration.

CI covers the existing tests for grid coordinates, exact code labels, data-count consistency, A2/A4 output, MASTER immutability, palette constraints, edit review gates, mock MediaPipe masks and tamper detection. Model weights are not bundled or downloaded. Optional **actual** MediaPipe inference must be separately exercised with a locally supplied, authorized model and visually inspected category overlays.

Release discipline: always confirm the current `main` HEAD before changing files; never overwrite a newer release from an older ZIP. Any new visual output must be derived from the actual verified bead-code matrix and visually reviewed as a **candidate** before it is approved. A green CI check is not visual approval.

Official guide: https://docs.github.com/en/actions/tutorials/build-and-test-code/python
