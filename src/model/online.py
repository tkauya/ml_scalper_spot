from __future__ import annotations
import joblib, numpy as np
from typing import List
from sklearn.linear_model import SGDClassifier
FEATURES=["spread_bps","imb","micro_dev","vol","ofi"]
class OnlineSGD:
    def __init__(self, alpha: float=1e-4, eta0: float=0.01, penalty: str="l2", random_state: int=42)->None:
        self.clf=SGDClassifier(loss="log_loss", alpha=alpha, learning_rate="optimal", eta0=eta0, penalty=penalty, random_state=random_state); self.inited=False
    def _Xy(self, feats: List[dict], y: List[int]):
        X=np.array([[f[k] for k in FEATURES] for f in feats], dtype=np.float64); yy=np.array(y, dtype=np.int64); return X, yy
    def partial_fit(self, feats: List[dict], y: List[int])->None:
        X,yy=self._Xy(feats,y); import numpy as _np; classes=_np.array([-1,0,1])
        if not self.inited: self.clf.partial_fit(X,yy,classes=classes); self.inited=True
        else: self.clf.partial_fit(X,yy)
    def predict_proba_up(self, feat: dict)->float:
        X=np.array([[feat[k] for k in FEATURES]], dtype=np.float64)
        if not self.inited: return 0.5
        proba=self.clf.predict_proba(X)[0]; idx_pos=list(self.clf.classes_).index(1); return float(proba[idx_pos])
    def save(self, path: str)->None: joblib.dump(self.clf, path)
    def load(self, path: str)->None:
        self.clf=joblib.load(path); self.inited=True
