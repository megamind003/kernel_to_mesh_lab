import numpy as np
import pandas as pd
from xgboost import XGBClassifier
import pickle
import os


class FraudModelTrainer:
    def __init__(self, output_dir: str = "./models"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
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

    def generate_synthetic_data(self, n_samples: int = 50000) -> tuple[pd.DataFrame, np.ndarray]:
        np.random.seed(42)
        
        normal_transactions = int(n_samples * 0.95)
        fraud_transactions = n_samples - normal_transactions
        
        normal_data = {
            "amount": np.random.lognormal(4.5, 1.2, normal_transactions),
            "user_risk_score": np.random.randint(0, 50, normal_transactions),
            "avg_amount": np.random.lognormal(4.3, 1.0, normal_transactions),
            "txn_per_hour": np.random.randint(0, 8, normal_transactions),
            "travel_speed": np.random.uniform(0, 100, normal_transactions),
            "merchant_new": np.random.choice([0, 1], normal_transactions, p=[0.9, 0.1]),
            "hour": np.random.randint(6, 23, normal_transactions),
        }
        
        fraud_data = {
            "amount": np.random.lognormal(6.0, 1.5, fraud_transactions),
            "user_risk_score": np.random.randint(50, 100, fraud_transactions),
            "avg_amount": np.random.lognormal(4.0, 0.8, fraud_transactions),
            "txn_per_hour": np.random.randint(8, 50, fraud_transactions),
            "travel_speed": np.random.uniform(100, 5000, fraud_transactions),
            "merchant_new": np.random.choice([0, 1], fraud_transactions, p=[0.3, 0.7]),
            "hour": np.random.randint(0, 6, fraud_transactions),
        }
        
        df_normal = pd.DataFrame(normal_data)
        df_fraud = pd.DataFrame(fraud_data)
        
        df = pd.concat([df_normal, df_fraud], ignore_index=True)
        labels = np.array([0] * normal_transactions + [1] * fraud_transactions)
        
        df["amount_ratio"] = df["amount"] / (df["avg_amount"] + 1)
        
        return df, labels

    def train_and_export(self) -> None:
        print("Generating synthetic training data...")
        X, y = self.generate_synthetic_data(50000)
        
        print(f"Training set: {X.shape}")
        print(f"Fraud rate: {y.mean():.2%}")
        
        print("\nTraining XGBoost classifier...")
        model = XGBClassifier(
            n_estimators=50,
            max_depth=4,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            objective='binary:logistic',
            random_state=42,
            n_jobs=-1
        )
        
        model.fit(X, y)
        
        model_path = os.path.join(self.output_dir, "fraud_detector.pkl")
        with open(model_path, "wb") as f:
            pickle.dump(model, f)
        
        print(f"\nModel saved to {model_path}")
        print("Training complete!")


if __name__ == "__main__":
    trainer = FraudModelTrainer()
    trainer.train_and_export()
