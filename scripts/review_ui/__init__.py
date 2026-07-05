"""Gold-card human-review web app: blind export, review server, annotation merge.

Three tracked entry points (data stays in gitignored ``internal/``):

* ``export_batch`` — build the blind review batch from ``internal/calibration/``
  (strip every prior label at the source).
* ``app`` — self-contained Flask review server (PEP 723; run via ``uv run``).
* ``merge_annotations`` — merge exported blind labels back into the gold cards.
"""
