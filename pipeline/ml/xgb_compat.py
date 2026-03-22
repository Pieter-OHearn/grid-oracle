"""Utilities for using XGBoost's sklearn wrappers without installing sklearn.

The production environment ships the lightweight xgboost wheel but omits
scikit-learn itself.  XGBoost guards its sklearn-style estimators behind a
runtime flag (SKLEARN_INSTALLED) and raises ImportError when that dependency
is missing, even though the estimators themselves only rely on mixin classes.

By flipping the flag to ``True`` inside xgboost.sklearn we unblock the
regressor classes while still relying on the stub mixins exposed by
``xgboost.compat``.  This mirrors the upstream behaviour prior to the guard
and keeps our training/prediction pipeline working inside minimal runtimes.
"""

import sys
import types

from xgboost import compat as xgb_compat
from xgboost import sklearn as xgb_sklearn

if not xgb_sklearn.SKLEARN_INSTALLED:
    xgb_sklearn.SKLEARN_INSTALLED = True


def _ensure_base_methods(cls):
    if hasattr(cls, "get_params") and hasattr(cls, "set_params"):
        return

    def get_params(self, deep: bool = True):
        return {k: v for k, v in self.__dict__.items() if not k.endswith("_")}

    def set_params(self, **params):
        for key, value in params.items():
            setattr(self, key, value)
        return self

    cls.get_params = get_params  # type: ignore[attr-defined]
    cls.set_params = set_params  # type: ignore[attr-defined]


for _base in (xgb_compat.XGBModelBase, xgb_compat.XGBClassifierBase, xgb_compat.XGBRegressorBase):
    _ensure_base_methods(_base)

if not hasattr(xgb_compat.XGBRegressorBase, "_estimator_type"):
    xgb_compat.XGBRegressorBase._estimator_type = "regressor"  # type: ignore[attr-defined]
if not hasattr(xgb_compat.XGBClassifierBase, "_estimator_type"):
    xgb_compat.XGBClassifierBase._estimator_type = "classifier"  # type: ignore[attr-defined]

if "sklearn" not in sys.modules:
    sklearn_stub = types.ModuleType("sklearn")
    base_module = types.ModuleType("sklearn.base")

    def is_classifier(estimator) -> bool:
        return getattr(estimator, "_estimator_type", None) == "classifier"

    base_module.is_classifier = is_classifier  # type: ignore[attr-defined]
    base_module.BaseEstimator = xgb_compat.XGBModelBase  # type: ignore[attr-defined]
    base_module.ClassifierMixin = xgb_compat.XGBClassifierBase  # type: ignore[attr-defined]
    base_module.RegressorMixin = xgb_compat.XGBRegressorBase  # type: ignore[attr-defined]

    sklearn_stub.base = base_module  # type: ignore[attr-defined]
    sys.modules["sklearn"] = sklearn_stub
    sys.modules["sklearn.base"] = base_module

from xgboost import XGBRegressor  # noqa: E402

__all__ = ["XGBRegressor"]
