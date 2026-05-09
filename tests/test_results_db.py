from spiral_sandbox.io.results_db import MetricRow, ResultsDB


def test_schema_init_and_roundtrip(tmp_path):
    db = ResultsDB(tmp_path / "spiral.db")
    run_id = db.begin_run(notes="unit-test")
    assert run_id == 1
    db.write_metric(
        run_id,
        MetricRow(
            scene="bunny_baseline",
            density="medium",
            method="point_cloud",
            metric="chamfer",
            value=0.0125,
            extra={"n_pred": 5000},
        ),
    )
    got = db.query_metric("bunny_baseline", "medium", "point_cloud", "chamfer")
    assert got == 0.0125


def test_unique_constraint_overwrites(tmp_path):
    db = ResultsDB(tmp_path / "spiral.db")
    rid = db.begin_run()
    row = MetricRow(
        scene="s", density="medium", method="m", metric="chamfer", value=1.0
    )
    db.write_metric(rid, row)
    row.value = 2.0
    db.write_metric(rid, row)
    assert db.query_metric("s", "medium", "m", "chamfer") == 2.0


def test_reconstruction_row(tmp_path):
    db = ResultsDB(tmp_path / "spiral.db")
    rid = db.begin_run()
    db.write_reconstruction(
        rid,
        scene="bunny_baseline",
        density="medium",
        method="point_cloud",
        artifact_dir=tmp_path / "artifacts/x",
        metadata={"n_points": 12345},
    )
    # Sanity: a second insert with the same key should overwrite, not error.
    db.write_reconstruction(
        rid,
        scene="bunny_baseline",
        density="medium",
        method="point_cloud",
        artifact_dir=tmp_path / "artifacts/y",
        metadata={"n_points": 67890},
    )
