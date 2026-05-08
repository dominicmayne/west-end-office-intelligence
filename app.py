from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from sklearn.linear_model import LinearRegression

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"status": "API running"}

@app.get("/predictions")
def predictions():

    data = pd.read_csv("../data/west_end_office_data.csv")

    data["area_code"] = data["area"].astype("category").cat.codes

    X = data[["year", "rent_psf", "area_code"]]
    y = data["vacancy_rate"]

    model = LinearRegression()
    model.fit(X, y)

    data["predicted"] = model.predict(X)

    # -----------------------------
    # 🔥 NEW: Intelligence layer
    # -----------------------------

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

    results = []

    for _, row in data.iterrows():
        results.append({
            "area": row["area"],
            "year": row["year"],
            "vacancy": float(row["vacancy_rate"]),
            "predicted": float(row["predicted"]),
            "signal": get_signal(row["predicted"]),
            "insight": get_insight(row["area"], row["predicted"])
        })

    return results

    @app.get("/test")
def test():
    return {"status": "working"}
