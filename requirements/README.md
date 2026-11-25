# Separate execution environments

Use Python 3.13.9 with `engineering-recorded.txt` and Python 3.13.7 with `model-and-spark-observed.txt`. The root requirements selects engineering. Do not merge the different NumPy/pandas pins. Java 17 is an external MLlib prerequisite.

On 25 November both new Windows venvs passed installation, pip check and imports. The exact resulting package lists are `engineering-clean-freeze-20261125.txt` and `model-clean-freeze-20261125.txt` (24 and 16 packages). Status and logs are in S5. These are observed clean-install freezes, not a reconstruction of all historical native binaries or a full scientific run in those venvs. Earlier observed/partial requirements remain for provenance.

For repeat installation use the corresponding recipe or observed freeze in a new environment; record Python version, package availability, pip freeze and pip check. Do not relax exact scientific input/version guards.
