from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
import pandas as pd
from sklearn.linear_model import LinearRegression
import os
import httpx
from weasyprint import HTML
from datetime import datetime

app = FastAPI()

# -------------------------
# CORS
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
                    "messages": [{"role": "user", "content": prompt}]
                }
            )
            result = response.json()
            if "content" not in result:
                return {"commentary": f"API error: {result.get('error', {}).get('message', str(result))}"}
            return {"commentary": result["content"][0]["text"]}
    except Exception as e:
        return {"commentary": f"Commentary unavailable: {str(e)}"}

# -------------------------
# PDF Report endpoint
# -------------------------
@app.get("/report/{area}")
async def generate_report(area: str):

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    area_data = data[data["area"] == area].copy()

    if area_data.empty:
        return {"error": "No data found for this area."}

    latest = area_data.iloc[-1]
    first = area_data.iloc[0]

    avg_vacancy = float(area_data["predicted"].mean())
    score = max(0, min(100, round(100 - (avg_vacancy * 10))))
    rent_change = float(latest["rent_psf"]) - float(first["rent_psf"])
    latest_takeup = int(latest["takeup_sqft"])
    sentiment = latest["sentiment"]
    quarters = len(area_data)

    # Signal
    if avg_vacancy < 5:
        signal_text = "STRONG MARKET"
        signal_color = "#22c55e"
        signal_bg = "rgba(34,197,94,0.15)"
    elif avg_vacancy < 7:
        signal_text = "MONITOR"
        signal_color = "#f59e0b"
        signal_bg = "rgba(245,158,11,0.15)"
    else:
        signal_text = "WEAKENING"
        signal_color = "#ef4444"
        signal_bg = "rgba(239,68,68,0.15)"

    # Get AI commentary
    commentary_text = ""
    if api_key:
        prompt = f"""You are a senior commercial real estate analyst at an institutional property research firm covering Central London office markets.

Write a concise, professional market commentary paragraph (4-6 sentences) for the {area} office submarket based on the following data:

- Tracked period: {int(first['year'])} {first['quarter']} to {int(latest['year'])} {latest['quarter']} ({quarters} quarters)
- Prime rent: £{float(first['rent_psf'])} psf to £{float(latest['rent_psf'])} psf (change of £{rent_change:+.0f} psf)
- Average forecast vacancy: {avg_vacancy:.2f}%
- Latest quarterly take-up: {latest_takeup:,} sq ft
- Market sentiment: {sentiment}

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
                        "messages": [{"role": "user", "content": prompt}]
                    }
                )
                result = response.json()
                if "content" in result:
                    commentary_text = result["content"][0]["text"]
        except:
            commentary_text = "Commentary unavailable at this time."

    # Build table rows
    table_rows = ""
    for _, row in area_data.iterrows():
        sentiment_colors = {
            "Tightening": ("#22c55e", "rgba(34,197,94,0.1)"),
            "Strong": ("#60a5fa", "rgba(59,130,246,0.1)"),
            "Improving": ("#a855f7", "rgba(168,85,247,0.1)"),
            "Active": ("#f59e0b", "rgba(245,158,11,0.1)"),
            "Balanced": ("#94a3b8", "rgba(148,163,184,0.1)"),
            "Neutral": ("#94a3b8", "rgba(148,163,184,0.1)"),
        }
        sc = sentiment_colors.get(row["sentiment"], ("#94a3b8", "rgba(148,163,184,0.1)"))
        table_rows += f"""
        <tr>
            <td><strong>{int(row['year'])} {row['quarter']}</strong></td>
            <td>£{row['rent_psf']}</td>
            <td>{row['vacancy_rate']:.1f}%</td>
            <td>{row['predicted']:.2f}%</td>
            <td>{int(row['takeup_sqft']):,}</td>
            <td><span style="background:{sc[1]};color:{sc[0]};padding:2px 8px;border-radius:999px;font-size:10px;font-weight:600;">{row['sentiment']}</span></td>
        </tr>
        """

    # Build rent trend sparkline data
    rent_values = area_data["rent_psf"].tolist()
    vac_values = [round(v, 2) for v in area_data["predicted"].tolist()]
    period_labels = [f"{int(r['year'])} {r['quarter']}" for _, r in area_data.iterrows()]

    generated_date = datetime.now().strftime("%d %B %Y")

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="UTF-8">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
            background: #ffffff;
            color: #1e293b;
            font-size: 11px;
            padding: 40px;
        }}

        /* HEADER */
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            padding-bottom: 20px;
            border-bottom: 2px solid #1e293b;
            margin-bottom: 24px;
        }}
        .header-left h1 {{
            font-size: 22px;
            font-weight: 800;
            color: #0f172a;
            letter-spacing: -0.5px;
        }}
        .header-left h1 span {{ color: #3b82f6; }}
        .header-left p {{
            font-size: 11px;
            color: #64748b;
            margin-top: 4px;
        }}
        .header-right {{
            text-align: right;
        }}
        .header-right .date {{
            font-size: 11px;
            color: #64748b;
        }}
        .header-right .powered {{
            font-size: 10px;
            color: #a855f7;
            margin-top: 4px;
            font-weight: 600;
        }}

        /* SUBMARKET TITLE */
        .submarket-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }}
        .submarket-title {{
            font-size: 28px;
            font-weight: 800;
            color: #0f172a;
        }}
        .submarket-subtitle {{
            font-size: 12px;
            color: #64748b;
            margin-top: 2px;
        }}
        .signal {{
            padding: 8px 18px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 700;
            background: {signal_bg};
            color: {signal_color};
            border: 1px solid {signal_color};
        }}

        /* KPI ROW */
        .kpi-row {{
            display: flex;
            gap: 12px;
            margin-bottom: 24px;
        }}
        .kpi-box {{
            flex: 1;
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 14px 16px;
        }}
        .kpi-box .label {{
            font-size: 9px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #94a3b8;
            margin-bottom: 6px;
        }}
        .kpi-box .val {{
            font-size: 22px;
            font-weight: 800;
            color: #0f172a;
        }}
        .kpi-box .sub {{
            font-size: 9px;
            color: #94a3b8;
            margin-top: 2px;
        }}

        /* COMMENTARY */
        .commentary-section {{
            background: #f8fafc;
            border-left: 3px solid #a855f7;
            border-radius: 0 10px 10px 0;
            padding: 16px 20px;
            margin-bottom: 24px;
        }}
        .commentary-label {{
            font-size: 9px;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            color: #a855f7;
            font-weight: 700;
            margin-bottom: 8px;
        }}
        .commentary-text {{
            font-size: 11px;
            color: #334155;
            line-height: 1.8;
        }}

        /* TABLE */
        .table-section {{ margin-bottom: 24px; }}
        .section-label {{
            font-size: 9px;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            color: #64748b;
            font-weight: 700;
            margin-bottom: 10px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 10px;
        }}
        th {{
            text-align: left;
            padding: 8px 10px;
            background: #f1f5f9;
            color: #64748b;
            font-size: 9px;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            border-bottom: 1px solid #e2e8f0;
        }}
        td {{
            padding: 8px 10px;
            border-bottom: 1px solid #f1f5f9;
            color: #334155;
        }}
        tr:last-child td {{ border-bottom: none; }}

        /* FOOTER */
        .footer {{
            border-top: 1px solid #e2e8f0;
            padding-top: 14px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .footer-left {{
            font-size: 9px;
            color: #94a3b8;
        }}
        .footer-right {{
            font-size: 9px;
            color: #94a3b8;
            text-align: right;
        }}
        .footer-right strong {{ color: #64748b; }}

        /* DISCLAIMER */
        .disclaimer {{
            font-size: 8px;
            color: #cbd5e1;
            margin-top: 8px;
            line-height: 1.5;
        }}
    </style>
    </head>
    <body>

    <!-- HEADER -->
    <div class="header">
        <div class="header-left">
            <h1>West End <span>Office Intelligence</span></h1>
            <p>Institutional-grade AI-assisted leasing analytics · Central London</p>
        </div>
        <div class="header-right">
            <div class="date">Generated: {generated_date}</div>
            <div class="powered">✦ Powered by Claude · Anthropic</div>
        </div>
    </div>

    <!-- SUBMARKET TITLE -->
    <div class="submarket-header">
        <div>
            <div class="submarket-title">{area}</div>
            <div class="submarket-subtitle">Submarket Research Note · {int(first['year'])} {first['quarter']} — {int(latest['year'])} {latest['quarter']}</div>
        </div>
        <div class="signal">{signal_text}</div>
    </div>

    <!-- KPI ROW -->
    <div class="kpi-row">
        <div class="kpi-box">
            <div class="label">Prime Rent</div>
            <div class="val">£{float(latest['rent_psf']):.0f}</div>
            <div class="sub">£ per sq ft</div>
        </div>
        <div class="kpi-box">
            <div class="label">Forecast Vacancy</div>
            <div class="val">{avg_vacancy:.1f}%</div>
            <div class="sub">AI-predicted average</div>
        </div>
        <div class="kpi-box">
            <div class="label">Latest Take-Up</div>
            <div class="val">{latest_takeup:,}</div>
            <div class="sub">sq ft leased</div>
        </div>
        <div class="kpi-box">
            <div class="label">Market Health</div>
            <div class="val">{score}/100</div>
            <div class="sub">AI-derived score</div>
        </div>
        <div class="kpi-box">
            <div class="label">Sentiment</div>
            <div class="val" style="font-size:16px;">{sentiment}</div>
            <div class="sub">Latest quarter</div>
        </div>
    </div>

    <!-- COMMENTARY -->
    <div class="commentary-section">
        <div class="commentary-label">✦ AI Market Commentary · Claude</div>
        <div class="commentary-text">{commentary_text}</div>
    </div>

    <!-- DATA TABLE -->
    <div class="table-section">
        <div class="section-label">Quarterly Data Breakdown</div>
        <table>
            <thead>
                <tr>
                    <th>Period</th>
                    <th>Prime Rent (£ psf)</th>
                    <th>Vacancy Rate</th>
                    <th>Forecast Vacancy</th>
                    <th>Take-Up (sq ft)</th>
                    <th>Sentiment</th>
                </tr>
            </thead>
            <tbody>
                {table_rows}
            </tbody>
        </table>
    </div>

    <!-- FOOTER -->
    <div class="footer">
        <div class="footer-left">
            <strong>West End Office Intelligence Platform</strong><br>
            Built by Dominic Mayne · Confidential Research Note · © {datetime.now().year}
        </div>
        <div class="footer-right">
            <strong>AI-Assisted Analytics</strong><br>
            Powered by Claude · Anthropic
        </div>
    </div>

    <div class="disclaimer">
        This report has been generated using AI-assisted analytics and should be used for informational purposes only.
        Data sources include published market reports from Savills, CBRE, Colliers, BNP Paribas Real Estate and Avison Young.
        West End Office Intelligence Platform accepts no liability for decisions made based on this report.
    </div>

    </body>
    </html>
    """

    try:
        pdf_bytes = HTML(string=html_content).write_pdf()
        filename = f"West_End_Office_{area.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        return {"error": f"PDF generation failed: {str(e)}"}

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