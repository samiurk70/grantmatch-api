"""XGBoost reranker — loads trained model or falls back to a weighted heuristic."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np

from app.config import get_settings
from app.models.db_models import Grant
from app.models.schemas import ApplicantProfile, FactorExplanation
from app.utils.feature_extractor import FEATURE_NAMES, features_to_array

logger = logging.getLogger(__name__)

# The XGBoost model was trained on 30 synthetic grants and outputs near-constant
# probabilities (~0.78) on all real inputs, collapsing score variance.
# Set to True only after retraining on real production grant data.
_MODEL_ENABLED = False

# Weights for the heuristic scorer — must sum to 100
_HEURISTIC_WEIGHTS: dict[str, float] = {
    "semantic_similarity": 40.0,
    "sector_overlap":      25.0,
    "org_type_match":      15.0,
    "trl_match":           10.0,
    "is_open":              5.0,
    "region_match":         5.0,
    # remaining features contribute 0 to the score but appear in explanations
    "days_to_deadline":     0.0,
    "funding_fit":          0.0,
    "description_length":   0.0,
}


def _direction(feature_name: str, value: float) -> str:
    """Heuristic direction: positive means the feature helps the grant's score."""
    thresholds = {
        "semantic_similarity": 0.30,
        "sector_overlap":      0.01,
        "org_type_match":      0.50,
        "trl_match":           0.50,
        "region_match":        0.50,
        "is_open":             0.50,
        "days_to_deadline":    0.30,
        "funding_fit":         0.50,
        "description_length":  0.20,
    }
    return "positive" if value >= thresholds.get(feature_name, 0.5) else "negative"


def _top3_factors(features: dict[str, float], weights: dict[str, float]) -> list[FactorExplanation]:
    """Derive exactly 3 FactorExplanation items from feature contributions."""
    contributions = [
        (name, features[name] * weights.get(name, 0.0), features[name])
        for name in FEATURE_NAMES
    ]
    # Sort by absolute contribution descending, break ties by feature value
    contributions.sort(key=lambda t: (-abs(t[1]), -t[2]))
    top3 = contributions[:3]
    return [
        FactorExplanation(
            factor_name=name,
            direction=_direction(name, feat_val),
            impact=round(float(feat_val), 4),
        )
        for name, _, feat_val in top3
    ]


class GrantReranker:
    """
    Scores a (grant, profile) pair.

    If a trained XGBoost model exists at MODEL_PATH it is used; otherwise
    a weighted linear heuristic provides scores in the same 0–100 range.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.model: Any | None = None
        self._explainer: Any | None = None
        path = Path(settings.model_path)

        if path.exists():
            try:
                import joblib
                self.model = joblib.load(str(path))
                logger.info("XGBoost reranker loaded from %s.", path)
                try:
                    import shap
                    self._explainer = shap.TreeExplainer(self.model)
                    logger.info("SHAP TreeExplainer ready.")
                except Exception as exc:
                    logger.warning("SHAP explainer unavailable: %s", exc)
            except Exception as exc:
                logger.warning("Failed to load reranker model, using heuristic: %s", exc)
        else:
            logger.info("No model at %s — using heuristic scoring.", path)

    def score(
        self,
        grant: Grant,  # noqa: ARG002 — available for future model extensions
        profile: ApplicantProfile,  # noqa: ARG002
        semantic_score: float,
        features: dict[str, float],
    ) -> tuple[float, list[FactorExplanation]]:
        """
        Return (score_0_to_100, top_3_factors).

        With model: score = predict_proba(positive class) * 100,
                    factors derived from SHAP values.
        Without:    score = weighted sum of features (max 100),
                    factors derived from feature contributions.
        """
        if self.model is not None and _MODEL_ENABLED:
            return self._model_score(features)
        return self._heuristic_score(features)

    # ------------------------------------------------------------------

    def _heuristic_score(
        self, features: dict[str, float]
    ) -> tuple[float, list[FactorExplanation]]:
        score = sum(
            features[name] * weight
            for name, weight in _HEURISTIC_WEIGHTS.items()
        )
        score = max(0.0, min(100.0, score))
        factors = _top3_factors(features, _HEURISTIC_WEIGHTS)
        return round(score, 2), factors

    def _model_score(
        self, features: dict[str, float]
    ) -> tuple[float, list[FactorExplanation]]:
        X = features_to_array(features).reshape(1, -1)
        try:
            probs = self.model.predict_proba(X)[0]  # shape: (n_classes,)
            # Weighted expected value: labels 0=irrelevant → 3=strong, scaled to 0–100.
            n = len(probs)
            score = round(float(sum(i / (n - 1) * p for i, p in enumerate(probs))) * 100.0, 2)
        except AttributeError:
            # Fallback if model has no predict_proba (e.g. regressor)
            raw = float(self.model.predict(X)[0])
            score = round(max(0.0, min(100.0, raw * 100.0)), 2)

        factors = self._shap_factors(features, X)
        return score, factors

    def _shap_factors(
        self, features: dict[str, float], X: np.ndarray
    ) -> list[FactorExplanation]:
        if self._explainer is None:
            return _top3_factors(features, _HEURISTIC_WEIGHTS)
        try:
            shap_values = self._explainer.shap_values(X)
            # Binary classifier: shap_values may be [neg_class, pos_class]
            if isinstance(shap_values, list):
                sv = shap_values[1][0]
            else:
                sv = shap_values[0]

            pairs = sorted(
                zip(FEATURE_NAMES, sv),
                key=lambda t: abs(t[1]),
                reverse=True,
            )
            return [
                FactorExplanation(
                    factor_name=name,
                    direction="positive" if val >= 0 else "negative",
                    impact=round(float(min(abs(val), 1.0)), 4),
                )
                for name, val in pairs[:3]
            ]
        except Exception as exc:
            logger.warning("SHAP explanation failed: %s", exc)
            return _top3_factors(features, _HEURISTIC_WEIGHTS)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_reranker: GrantReranker | None = None


def get_reranker() -> GrantReranker:
    global _reranker
    if _reranker is None:
        _reranker = GrantReranker()
    return _reranker
