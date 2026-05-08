from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from sklearn.linear_model import LinearRegression
import os
import httpx

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
# Load data + train model ONCE at startup
# -------------------------
data = pd.read_csv("data/west_end_office_data.csv")

data["year"] = pd.to_numeric(data["year"])
data["rent_psf"] = pd.to_numeric(data["rent_psf"])
data["vacancy_rate"] = pd.to_numeric(data["vacancy_rate"])
data["takeup_sqft"] = pd.to_numeric(data["takeup_sqft"])

AREA_CODES = {area: i for i, area in enumerate(sorted(data["area"].unique()))}
data["area_code"] = data["area"].map(AREA_CODES)

QUARTER_CODES = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}
data["quarter_code"] = data["quarter"].map(QUARTER_CODES)

X = data[["year", "quarter_code", "rent_psf", "area_code"]]
y = data["vacancy_rate"]

model = LinearRegression()
model.fit(X, y)

data["predicted"] = model.predict(X)

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

    def get_signal(v):
        if v < 5:
            return "🟢 Attractive"
        elif v < 7:
            return "🟡 Neutral"
        return "🔴 Weakening"

    def get_insight(area, v):
        return f"{area} shows current vacancy at {v:.1f}% with AI-adjusted market interpretation."

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
# Commentary endpoint (Claude AI)
# -------------------------
@app.get("/commentary/{area}")
async def commentary(area: str):

    api_key = os.environ.get("ANTHROPIC_API_KEY")

    if not api_key:
        return {"commentary": "API key not configured."}

    area_data = data[data["area"] == area].copy()

    if area_data.empty:
        return {"commentary": "No data available for this submarket."}

    latest = area_data.iloc[-1]
    first = area_data.iloc[0]

    rent_change = float(latest["rent_psf"]) - float(first["rent_psf"])
    avg_vacancy = float(area_data["predicted"].mean())
    latest_takeup = int(latest["takeup_sqft"])
    sentiment = latest["sentiment"]
    quarters = len(area_data)

    prompt = f"""You are a senior commercial real estate analyst at an institutional property research firm covering Central London office markets.

Write a concise, professional market commentary paragraph (4-6 sentences) for the {area} office submarket based on the following data:

- Tracked period: {int(first['year'])} {first['quarter']} to {int(latest['year'])} {latest['quarter']} ({quarters} quarters)
- Prime rent: £{float(first['rent_psf'])} psf to £{float(latest['rent_psf'])} psf (change of £{rent_change:+.0f} psf)
- Average forecast vacancy: {avg_vacancy:.2f}%
- Latest quarterly take-up: {latest_takeup:,} sq ft
- Market sentiment: {sentiment}
- AI forecast vacancy (latest): {float(latest['predicted']):.2f}%

Write in the style of a Savills or CBRE research note. Be specific, use the data, and give a forward-looking view. Do not use bullet points. Do not start with '{area}'. Sound authoritative but concise."""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": "claude-sonnet-4-5",
                    "max_tokens": 300,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ]
                }
            )

            result = response.json()

            if "content" not in result:
                return {"commentary": f"API error: {result.get('error', {}).get('message', str(result))}"}

            commentary_text = result["content"][0]["text"]
            return {"commentary": commentary_text}

    except Exception as e:
        return {"commentary": f"Commentary unavailable: {str(e)}"}

# -------------------------
# Test endpoint
# -------------------------
@app.get("/test")
def test():
    return {"status": "working"}

# -------------------------
# Area codes endpoint
# -------------------------
@app.get("/area-codes")
def area_codes():
    return AREA_CODES

# -------------------------
# Railway / local startup
# -------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)