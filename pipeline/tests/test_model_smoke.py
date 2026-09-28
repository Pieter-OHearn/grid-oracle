"""Native CPU-only XGBoost compatibility check for the supported environment."""

import numpy as np
from xgboost import XGBRegressor

from pipeline.ml.predict import load_model
from pipeline.ml.train import save_model


def test_native_xgboost_model_saves_and_loads_on_cpu(tmp_path):
    """Exercise native sklearn/XGBoost integration without compatibility patches."""
    features = np.array([[0.0], [1.0], [2.0], [3.0]])
    target = np.array([4.0, 3.0, 2.0, 1.0])
    model = XGBRegressor(
        n_estimators=2,
        max_depth=1,
        n_jobs=1,
        random_state=42,
        tree_method="hist",
    )
    model.fit(features, target)

    artifact = tmp_path / "cpu-smoke.json"
    save_model(model, artifact)
    loaded = load_model(artifact)

    assert artifact.exists()
    assert loaded.predict(features).shape == target.shape
