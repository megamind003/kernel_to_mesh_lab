import numpy as np
import pickle
from typing import Dict, Any, Optional
import os


class MLInference:
    def __init__(self, model_path: str):
        self.model_path = model_path.replace('.onnx', '.pkl')
        self.model = None
        self.model_loaded = False
        
        self.feature_names = [
            "amount",
            "user_risk_score",
            "avg_amount",
            "txn_per_hour",
            "travel_speed",
            "merchant_new",
            "hour",
            "amount_ratio"
        ]

    async def load_model(self) -> None:
        if not os.path.exists(self.model_path):
            print(f"Warning: Model file not found at {self.model_path}")
            self.model_loaded = False
            return
        
        try:
            with open(self.model_path, "rb") as f:
                self.model = pickle.load(f)
            
            self.model_loaded = True
            print(f"Model loaded successfully from {self.model_path}")
            
        except Exception as e:
            print(f"Error loading model: {e}")
            self.model_loaded = False

    async def prepare_features(self, context: Dict[str, Any]) -> np.ndarray:
        amount = context.get("amount", 0.0)
        avg_amount = context.get("avg_amount", 1.0)
        
        amount_ratio = amount / (avg_amount + 1)
        
        features = [
            amount,
            context.get("user_risk_score", 0),
            avg_amount,
            context.get("transactions_per_hour", 0),
            context.get("travel_speed", 0.0),
            1.0 if context.get("merchant_new", False) else 0.0,
            context.get("hour", 12),
            amount_ratio
        ]
        
        return np.array([features], dtype=np.float32)

    async def predict(self, features: np.ndarray) -> float:
        if not self.model_loaded or self.model is None:
            return 0.0
        
        try:
            probabilities = self.model.predict_proba(features)
            fraud_probability = float(probabilities[0][1])
            return fraud_probability
            
        except Exception as e:
            print(f"Inference error: {e}")
            return 0.0

    async def predict_from_context(self, context: Dict[str, Any]) -> float:
        features = await self.prepare_features(context)
        return await self.predict(features)
