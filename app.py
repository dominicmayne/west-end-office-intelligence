from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
import pandas as pd
from sklearn.linear_model import LinearRegression
import os
import httpx
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
import json
import re

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Load data + train model ──
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

# ── Load seed deals ──
try:
    with open("data/deals_seed.json", "r") as f:
        SEED_DEALS = json.load(f)
except:
    SEED_DEALS = []

@app.get("/")
def home():
    return {"status": "API running"}

@app.get("/predictions")
def predictions():
    def get_signal(v):
        if v < 5: return "🟢 Attractive"
        elif v < 7: return "🟡 Neutral"
        return "🔴 Weakening"
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
            "insight": f"{row['area']} shows vacancy at {row['predicted']:.1f}%"
        })
    return results

@app.get("/commentary/{area}")
async def commentary(area: str):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"commentary": "API key not configured."}
    area_data = data[data["area"] == area].copy()
    if area_data.empty:
        return {"commentary": "No data available."}
    latest = area_data.iloc[-1]
    first = area_data.iloc[0]
    rent_change = float(latest["rent_psf"]) - float(first["rent_psf"])
    avg_vacancy = float(area_data["predicted"].mean())
    prompt = f"""You are a senior commercial real estate analyst covering Central London office markets.
Write a concise professional market commentary (4-6 sentences) for the {area} office submarket:
- Tracked period: {int(first['year'])} {first['quarter']} to {int(latest['year'])} {latest['quarter']}
- Prime rent: £{float(first['rent_psf'])} to £{float(latest['rent_psf'])} psf (£{rent_change:+.0f} psf change)
- Average forecast vacancy: {avg_vacancy:.2f}%
- Latest take-up: {int(latest['takeup_sqft']):,} sq ft
- Sentiment: {latest['sentiment']}
Style of Savills/CBRE research note. No bullets. Don't start with '{area}'."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": "claude-sonnet-4-5", "max_tokens": 300, "messages": [{"role": "user", "content": prompt}]}
            )
            result = response.json()
            if "content" not in result:
                return {"commentary": f"API error: {result.get('error', {}).get('message', str(result))}"}
            return {"commentary": result["content"][0]["text"]}
    except Exception as e:
        return {"commentary": f"Commentary unavailable: {str(e)}"}

@app.get("/live-data/{area}")
async def live_data(area: str):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"error": "API key not configured.", "live": False}
    area_data = data[data["area"] == area].copy()
    if area_data.empty:
        return {"error": "No baseline data.", "live": False}
    latest_baseline = area_data.iloc[-1]
    prompt = f"""You are a commercial real estate data analyst. Search for the most recent published market data for the {area} office submarket in Central London from Savills, CBRE, Colliers, Knight Frank, or BNP Paribas reports in 2024 or 2025.
Return ONLY a JSON object, no other text:
{{"rent_psf": <number or null>, "vacancy_rate": <number or null>, "takeup_sqft": <number or null>, "sentiment": "<Tightening|Strong|Improving|Balanced|Neutral|Weakening>", "source": "<source>", "period": "<e.g. Q3 2025>", "confidence": "<high|medium|low>", "notes": "<brief note>"}}"""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": "claude-sonnet-4-5", "max_tokens": 500, "tools": [{"type": "web_search_20250305", "name": "web_search"}], "messages": [{"role": "user", "content": prompt}]}
            )
            result = response.json()
            if "content" not in result:
                return {"live": False, "error": "No content", "fallback": _build_fallback(latest_baseline)}
            text_content = "".join(b.get("text", "") for b in result["content"] if b.get("type") == "text")
            json_match = re.search(r'\{[^{}]+\}', text_content, re.DOTALL)
            if not json_match:
                return {"live": False, "error": "Could not parse data", "fallback": _build_fallback(latest_baseline)}
            live = json.loads(json_match.group())
            rent = live.get("rent_psf") or float(latest_baseline["rent_psf"])
            vacancy = live.get("vacancy_rate") or float(latest_baseline["vacancy_rate"])
            takeup = live.get("takeup_sqft") or int(latest_baseline["takeup_sqft"])
            sentiment = live.get("sentiment") or latest_baseline["sentiment"]
            return {
                "live": True, "area": area,
                "rent_psf": rent, "vacancy_rate": vacancy,
                "takeup_sqft": takeup, "sentiment": sentiment,
                "source": live.get("source", "Web search"),
                "period": live.get("period", "Latest"),
                "confidence": live.get("confidence", "medium"),
                "notes": live.get("notes", ""),
                "baseline_rent": float(latest_baseline["rent_psf"]),
                "baseline_vacancy": float(latest_baseline["vacancy_rate"]),
                "rent_change": round(rent - float(latest_baseline["rent_psf"]), 1),
                "vacancy_change": round(vacancy - float(latest_baseline["vacancy_rate"]), 2)
            }
    except Exception as e:
        return {"live": False, "error": str(e), "fallback": _build_fallback(latest_baseline)}

def _build_fallback(row):
    return {"rent_psf": float(row["rent_psf"]), "vacancy_rate": float(row["vacancy_rate"]), "takeup_sqft": int(row["takeup_sqft"]), "sentiment": row["sentiment"]}

# ── DEALS ENDPOINT ──
@app.get("/deals/{area}")
async def deals(area: str):
    api_key = os.environ.get("ANTHROPIC_API_KEY")

    # Always return seed deals for this area first
    seed = [d for d in SEED_DEALS if d["area"] == area]

    if not api_key:
        return {"deals": seed, "source": "seed", "live": False}

    prompt = f"""Search the web for recent notable office lettings and transactions in the {area} submarket of Central London. Look for deals from 2024 and 2025 reported by Savills, CBRE, Knight Frank, Colliers, BNP Paribas, EG Propertylink, CoStar, or property press.

For each deal found return structured data. Return ONLY a JSON array, no other text:
[
  {{
    "occupier": "<company name>",
    "building": "<building name and address>",
    "size_sqft": <number>,
    "rent_psf": <number or null>,
    "sector": "<Financial Services|Technology|Professional Services|Media|Life Sciences|Flexible Office|Other>",
    "date": "<e.g. 2025-Q1>",
    "type": "<Letting|Pre-let|Sub-let|Renewal>",
    "grade": "<A|B>"
  }}
]

Return up to 8 deals. If rent is not publicly disclosed use null. Only include deals you are confident about from published sources."""

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": "claude-sonnet-4-5", "max_tokens": 1000, "tools": [{"type": "web_search_20250305", "name": "web_search"}], "messages": [{"role": "user", "content": prompt}]}
            )
            result = response.json()
            if "content" not in result:
                return {"deals": seed, "source": "seed", "live": False}

            text_content = "".join(b.get("text", "") for b in result["content"] if b.get("type") == "text")
            json_match = re.search(r'\[.*?\]', text_content, re.DOTALL)
            if not json_match:
                return {"deals": seed, "source": "seed", "live": False}

            live_deals = json.loads(json_match.group())

            # Add area to each live deal
            for d in live_deals:
                d["area"] = area

            # Merge: live deals first, then seed deals not already covered
            live_buildings = {d.get("building", "").lower() for d in live_deals}
            merged = live_deals + [d for d in seed if d.get("building", "").lower() not in live_buildings]

            return {"deals": merged[:12], "source": "live", "live": True}

    except Exception as e:
        return {"deals": seed, "source": "seed", "live": False, "error": str(e)}

# ── PDF REPORT ──
@app.get("/report/{area}")
async def generate_report(area: str):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    area_data = data[data["area"] == area].copy()
    if area_data.empty:
        return {"error": "No data found."}
    latest = area_data.iloc[-1]
    first = area_data.iloc[0]
    avg_vacancy = float(area_data["predicted"].mean())
    score = max(0, min(100, round(100 - (avg_vacancy * 10))))
    rent_change = float(latest["rent_psf"]) - float(first["rent_psf"])
    latest_takeup = int(latest["takeup_sqft"])
    sentiment = latest["sentiment"]
    quarters = len(area_data)
    if avg_vacancy < 5:
        signal_text, signal_color = "STRONG MARKET", colors.HexColor("#22c55e")
    elif avg_vacancy < 7:
        signal_text, signal_color = "MONITOR", colors.HexColor("#f59e0b")
    else:
        signal_text, signal_color = "WEAKENING", colors.HexColor("#ef4444")
    commentary_text = ""
    if api_key:
        prompt = f"""You are a senior commercial real estate analyst. Write a concise professional market commentary (4-6 sentences) for the {area} office submarket:
- Period: {int(first['year'])} {first['quarter']} to {int(latest['year'])} {latest['quarter']}
- Prime rent: £{float(first['rent_psf'])} to £{float(latest['rent_psf'])} psf
- Average forecast vacancy: {avg_vacancy:.2f}%
- Latest take-up: {latest_takeup:,} sq ft
- Sentiment: {sentiment}
Savills/CBRE style. No bullets. Don't start with '{area}'."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                    json={"model": "claude-sonnet-4-5", "max_tokens": 300, "messages": [{"role": "user", "content": prompt}]}
                )
                r = resp.json()
                if "content" in r:
                    commentary_text = r["content"][0]["text"]
        except:
            commentary_text = "Commentary unavailable."
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm, topMargin=20*mm, bottomMargin=20*mm)
    dark_navy = colors.HexColor("#0f172a")
    mid_slate = colors.HexColor("#334155")
    light_slate = colors.HexColor("#64748b")
    very_light = colors.HexColor("#f8fafc")
    border_color = colors.HexColor("#e2e8f0")
    purple = colors.HexColor("#a855f7")
    label_style = ParagraphStyle("label", fontSize=8, fontName="Helvetica-Bold", textColor=light_slate, spaceAfter=4, leading=10)
    body_style = ParagraphStyle("body", fontSize=10, fontName="Helvetica", textColor=mid_slate, leading=16, spaceAfter=0)
    small_style = ParagraphStyle("small", fontSize=8, fontName="Helvetica", textColor=light_slate, leading=12)
    section_label_style = ParagraphStyle("section_label", fontSize=8, fontName="Helvetica-Bold", textColor=purple, spaceAfter=6, leading=10)
    elements = []
    header_data = [[
        Paragraph('<font color="#0f172a"><b>West End </b></font><font color="#3b82f6"><b>Office Intelligence</b></font>', ParagraphStyle("h", fontSize=16, fontName="Helvetica-Bold")),
        Paragraph(f'<font color="#64748b">Generated: {datetime.now().strftime("%d %B %Y")}</font><br/><font color="#a855f7"><b>✦ Powered by Claude</b></font>', ParagraphStyle("hr", fontSize=9, fontName="Helvetica", alignment=TA_RIGHT, leading=14))
    ]]
    ht = Table(header_data, colWidths=[110*mm, 60*mm])
    ht.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("BOTTOMPADDING", (0,0), (-1,-1), 8)]))
    elements.append(ht)
    elements.append(HRFlowable(width="100%", thickness=1.5, color=dark_navy, spaceAfter=16))
    title_data = [[
        Paragraph(f'<b>{area}</b>', ParagraphStyle("at", fontSize=26, fontName="Helvetica-Bold", textColor=dark_navy)),
        Paragraph(f'<b>{signal_text}</b>', ParagraphStyle("sig", fontSize=11, fontName="Helvetica-Bold", textColor=signal_color, alignment=TA_RIGHT))
    ]]
    tt = Table(title_data, colWidths=[110*mm, 60*mm])
    tt.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("BOTTOMPADDING", (0,0), (-1,-1), 2)]))
    elements.append(tt)
    elements.append(Paragraph(f'Submarket Research Note · {int(first["year"])} {first["quarter"]} — {int(latest["year"])} {latest["quarter"]}', ParagraphStyle("sub", fontSize=10, fontName="Helvetica", textColor=light_slate)))
    elements.append(Spacer(1, 14))
    kpi_data = [
        [Paragraph("PRIME RENT", label_style), Paragraph("FORECAST VACANCY", label_style), Paragraph("LATEST TAKE-UP", label_style), Paragraph("MARKET HEALTH", label_style), Paragraph("SENTIMENT", label_style)],
        [Paragraph(f'<b>£{float(latest["rent_psf"]):.0f}</b>', ParagraphStyle("kv", fontSize=20, fontName="Helvetica-Bold", textColor=dark_navy)),
         Paragraph(f'<b>{avg_vacancy:.1f}%</b>', ParagraphStyle("kv", fontSize=20, fontName="Helvetica-Bold", textColor=dark_navy)),
         Paragraph(f'<b>{latest_takeup:,}</b>', ParagraphStyle("kv", fontSize=20, fontName="Helvetica-Bold", textColor=dark_navy)),
         Paragraph(f'<b>{score}/100</b>', ParagraphStyle("kv", fontSize=20, fontName="Helvetica-Bold", textColor=dark_navy)),
         Paragraph(f'<b>{sentiment}</b>', ParagraphStyle("kv", fontSize=16, fontName="Helvetica-Bold", textColor=dark_navy))],
        [Paragraph("£ per sq ft", small_style), Paragraph("AI-predicted avg", small_style), Paragraph("sq ft leased", small_style), Paragraph("AI-derived score", small_style), Paragraph("Latest quarter", small_style)]
    ]
    kpi_table = Table(kpi_data, colWidths=[34*mm]*5, rowHeights=[14, 22, 12])
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), very_light),
        ("BOX", (0,0), (0,-1), 0.5, border_color), ("BOX", (1,0), (1,-1), 0.5, border_color),
        ("BOX", (2,0), (2,-1), 0.5, border_color), ("BOX", (3,0), (3,-1), 0.5, border_color),
        ("BOX", (4,0), (4,-1), 0.5, border_color),
        ("LEFTPADDING", (0,0), (-1,-1), 8), ("RIGHTPADDING", (0,0), (-1,-1), 8),
        ("TOPPADDING", (0,0), (-1,0), 8), ("BOTTOMPADDING", (0,-1), (-1,-1), 8),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ]))
    elements.append(kpi_table)
    elements.append(Spacer(1, 16))
    elements.append(Paragraph("✦  AI MARKET COMMENTARY · CLAUDE", section_label_style))
    cb = Table([[Paragraph(commentary_text, body_style)]], colWidths=[170*mm])
    cb.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,-1), very_light), ("LEFTPADDING", (0,0), (-1,-1), 12), ("RIGHTPADDING", (0,0), (-1,-1), 12), ("TOPPADDING", (0,0), (-1,-1), 12), ("BOTTOMPADDING", (0,0), (-1,-1), 12), ("LINEBEFORE", (0,0), (0,-1), 3, purple)]))
    elements.append(cb)
    elements.append(Spacer(1, 16))
    elements.append(Paragraph("QUARTERLY DATA BREAKDOWN", section_label_style))
    table_rows_data = [["Period", "Prime Rent", "Vacancy", "Forecast", "Take-Up", "Sentiment"]]
    for _, row in area_data.iterrows():
        table_rows_data.append([f"{int(row['year'])} {row['quarter']}", f"£{row['rent_psf']}", f"{row['vacancy_rate']:.1f}%", f"{row['predicted']:.2f}%", f"{int(row['takeup_sqft']):,}", str(row['sentiment'])])
    dt = Table(table_rows_data, colWidths=[28*mm, 28*mm, 26*mm, 26*mm, 30*mm, 32*mm])
    dt.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), dark_navy), ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"), ("FONTSIZE", (0,0), (-1,0), 8),
        ("FONTSIZE", (0,1), (-1,-1), 9), ("FONTNAME", (0,1), (-1,-1), "Helvetica"),
        ("TEXTCOLOR", (0,1), (-1,-1), mid_slate), ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, very_light]),
        ("GRID", (0,0), (-1,-1), 0.3, border_color), ("LEFTPADDING", (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 8), ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6), ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ]))
    elements.append(dt)
    elements.append(Spacer(1, 20))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=border_color, spaceAfter=10))
    footer_data = [[
        Paragraph(f'<b>West End Office Intelligence</b><br/><font color="#94a3b8">Built by Dominic Mayne · © {datetime.now().year}</font>', ParagraphStyle("fl", fontSize=8, fontName="Helvetica", textColor=mid_slate, leading=12)),
        Paragraph('<font color="#a855f7"><b>✦ Powered by Claude · Anthropic</b></font>', ParagraphStyle("fr", fontSize=8, fontName="Helvetica", alignment=TA_RIGHT, leading=12))
    ]]
    ft = Table(footer_data, colWidths=[110*mm, 60*mm])
    ft.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP")]))
    elements.append(ft)
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("This report is for informational purposes only. Data sourced from Savills, CBRE, Colliers, BNP Paribas Real Estate and Avison Young. West End Office Intelligence accepts no liability for decisions made based on this report.", ParagraphStyle("disc", fontSize=7, fontName="Helvetica", textColor=colors.HexColor("#cbd5e1"), leading=10)))
    try:
        doc.build(elements)
        pdf_bytes = buffer.getvalue()
        filename = f"West_End_Office_{area.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
        return Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename={filename}"})
    except Exception as e:
        return {"error": f"PDF generation failed: {str(e)}"}

@app.get("/test")
def test():
    return {"status": "working"}

@app.get("/area-codes")
def area_codes():
    return AREA_CODES

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)