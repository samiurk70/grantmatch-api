"""XGBoost reranker — loads trained model or falls back to cosine-score heuristic."""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np

from app.config import get_settings

# Placeholder — full implementation added in a later step.


def load_reranker():
    """Load the XGBoost model from MODEL_PATH, or return None if not available."""
    settings = get_settings()
    path = Path(settings.model_path)
    if not path.exists():
        return None
    try:
        import xgboost as xgb
        model = xgb.Booster()
        model.load_model(str(path))
        return model
    except Exception:
        return None


def rerank(feature_matrix: np.ndarray, model=None) -> np.ndarray:
    """Score rows of feature_matrix. Falls back to first column (cosine sim) if no model."""
    if model is None:
        return feature_matrix[:, 0]
    import xgboost as xgb
    dmat = xgb.DMatrix(feature_matrix)
    return model.predict(dmat)
