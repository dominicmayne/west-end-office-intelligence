from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from sklearn.linear_model import LinearRegression
import os

app = FastAPI()

# -------------------------
# CORS (frontend access)
# -------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# Root
# -------------------------
@app.get("/")
def home():
    return {"status": "API running"}

# -------------------------
# Predictions endpoint
# -------------------------
@app.get("/predictions")
def predictions():

    # Load dataset (Railway-safe path)
    data = pd.read_csv("data/west_end_office_data.csv")

    # Clean numeric safety (prevents crashes if CSV has strings)
    data["year"] = pd.to_numeric(data["year"])
    data["rent_psf"] = pd.to_numeric(data["rent_psf"])
    data["vacancy_rate"] = pd.to_numeric(data["vacancy_rate"])
    data["takeup_sqft"] = pd.to_numeric(data["takeup_sqft"])

    # Encode categorical area
    data["area_code"] = data["area"].astype("category").cat.codes

    # -------------------------
    # Model
    # -------------------------
    X = data[["year", "rent_psf", "area_code"]]
    y = data["vacancy_rate"]

    model = LinearRegression()
    model.fit(X, y)

    data["predicted"] = model.predict(X)

    # -------------------------
    # Intelligence Layer
    # -------------------------
    def get_signal(v):
        if v < 5:
            return "🟢 Attractive"
        elif v < 7:
            return "🟡 Neutral"
        return "🔴 Weakening"

    def get_insight(area, v):
        return f"{area} shows current vacancy at {v:.1f}% with AI-adjusted market interpretation."

    # -------------------------
    # Response builder
    # -------------------------
    results = []

    for _, row in data.iterrows():
        results.append({
            "area": row["area"],
            "year": int(row["year"]),
            "quarter": row["quarter"],
            "rent_psf": float(row["rent_psf"]),
            "vacancy": float(row["vacancy_rate"]),
            "takeup_sqft": int(row["takeup_sqft"]),
            "sentiment": row["sentiment"],
            "predicted": float(row["predicted"]),
            "signal": get_signal(row["predicted"]),
            "insight": get_insight(row["area"], row["predicted"])
        })

    return results


# -------------------------
# Test endpoint
# -------------------------
@app.get("/test")
def test():
    return {"status": "working"}


# -------------------------
# Railway / local startup
# -------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)