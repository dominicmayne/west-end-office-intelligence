from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from sklearn.linear_model import LinearRegression
import uvicorn
import os

app = FastAPI()

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root endpoint
@app.get("/")
def home():
    return {"status": "API running"}

# Predictions endpoint
@app.get("/predictions")
def predictions():

    # Load data
    data = pd.read_csv("data/west_end_office_data.csv")

    # Encode areas
    data["area_code"] = data["area"].astype("category").cat.codes

    # Model setup
    X = data[["year", "rent_psf", "area_code"]]
    y = data["vacancy_rate"]

    model = LinearRegression()
    model.fit(X, y)

    # Predictions
    data["predicted"] = model.predict(X)

    # Intelligence layer
    def get_signal(v):
        if v < 5:
            return "🟢 Attractive"
        elif v < 7:
            return "🟡 Neutral"
        else:
            return "🔴 Weakening"

    def get_insight(area, v):
        if area == "Soho":
            return f"Soho is tightening due to strong tech demand (vacancy {v:.1f}%)"
        elif area == "Mayfair":
            return f"Mayfair remains ultra-prime with constrained supply (vacancy {v:.1f}%)"
        else:
            return f"{area} shows balanced leasing conditions (vacancy {v:.1f}%)"

    # Build response
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

# Test endpoint
@app.get("/test")
def test():
    return {"status": "working"}

# Railway startup
if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=PORT)