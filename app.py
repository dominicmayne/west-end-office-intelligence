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
# LIVE DATA endpoint (Claude + web search)
# -------------------------
@app.get("/live-data/{area}")
async def live_data(area: str):

    api_key = os.environ.get("ANTHROPIC_API_KEY")

    if not api_key:
        return {"error": "API key not configured.", "live": False}

    # Get our existing data as baseline
    area_data = data[data["area"] == area].copy()
    if area_data.empty:
        return {"error": "No baseline data found.", "live": False}

    latest_baseline = area_data.iloc[-1]

    current_year = datetime.now().year
    current_month = datetime.now().strftime("%B")

    prompt = f"""You are a commercial real estate data analyst. Search the web for the most recent published market data for the {area} office submarket in Central London.

Search for recent reports from Savills, CBRE, Colliers, Knight Frank, BNP Paribas Real Estate, or Avison Young covering {area} office market in 2024 or 2025.

Find the most current available figures for:
1. Prime rent (£ per sq ft per year) - look for "prime rent", "headline rent", "top rent"
2. Vacancy rate (%) - look for "vacancy rate", "availability rate"  
3. Take-up (sq ft) - look for "take-up", "leasing activity", "transactions"
4. Market sentiment - is the market described as tightening, strong, improving, stable, weakening?

Return ONLY a JSON object with no other text, no markdown, no explanation:
{{
  "rent_psf": <number or null>,
  "vacancy_rate": <number or null>,
  "takeup_sqft": <number or null>,
  "sentiment": "<Tightening|Strong|Improving|Balanced|Neutral|Weakening>",
  "source": "<name of report/source found>",
  "period": "<e.g. Q3 2025>",
  "confidence": "<high|medium|low>",
  "notes": "<brief note on what was found>"
}}

If you cannot find specific figures use null for that field. Use your best judgment from context clues in the reports."""

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": "claude-sonnet-4-5",
                    "max_tokens": 500,
                    "tools": [
                        {
                            "type": "web_search_20250305",
                            "name": "web_search"
                        }
                    ],
                    "messages": [
                        {"role": "user", "content": prompt}
                    ]
                }
            )

            result = response.json()

            if "content" not in result:
                return {
                    "live": False,
                    "error": result.get('error', {}).get('message', 'Unknown error'),
                    "fallback": _build_fallback(latest_baseline)
                }

            # Extract text from response (Claude may use tool then respond)
            text_content = ""
            for block in result["content"]:
                if block.get("type") == "text":
                    text_content += block.get("text", "")

            # Parse JSON from response
            json_match = re.search(r'\{[^{}]+\}', text_content, re.DOTALL)
            if not json_match:
                return {
                    "live": False,
                    "error": "Could not parse structured data",
                    "fallback": _build_fallback(latest_baseline)
                }

            live = json.loads(json_match.group())

            # Fill nulls with baseline data
            rent = live.get("rent_psf") or float(latest_baseline["rent_psf"])
            vacancy = live.get("vacancy_rate") or float(latest_baseline["vacancy_rate"])
            takeup = live.get("takeup_sqft") or int(latest_baseline["takeup_sqft"])
            sentiment = live.get("sentiment") or latest_baseline["sentiment"]

            return {
                "live": True,
                "area": area,
                "rent_psf": rent,
                "vacancy_rate": vacancy,
                "takeup_sqft": takeup,
                "sentiment": sentiment,
                "source": live.get("source", "Web search"),
                "period": live.get("period", "Latest available"),
                "confidence": live.get("confidence", "medium"),
                "notes": live.get("notes", ""),
                "baseline_rent": float(latest_baseline["rent_psf"]),
                "baseline_vacancy": float(latest_baseline["vacancy_rate"]),
                "rent_change": round(rent - float(latest_baseline["rent_psf"]), 1),
                "vacancy_change": round(vacancy - float(latest_baseline["vacancy_rate"]), 2)
            }

    except json.JSONDecodeError:
        return {
            "live": False,
            "error": "JSON parse error",
            "fallback": _build_fallback(latest_baseline)
        }
    except Exception as e:
        return {
            "live": False,
            "error": str(e),
            "fallback": _build_fallback(latest_baseline)
        }

def _build_fallback(row):
    return {
        "rent_psf": float(row["rent_psf"]),
        "vacancy_rate": float(row["vacancy_rate"]),
        "takeup_sqft": int(row["takeup_sqft"]),
        "sentiment": row["sentiment"]
    }

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

    if avg_vacancy < 5:
        signal_text = "STRONG MARKET"
        signal_color = colors.HexColor("#22c55e")
    elif avg_vacancy < 7:
        signal_text = "MONITOR"
        signal_color = colors.HexColor("#f59e0b")
    else:
        signal_text = "WEAKENING"
        signal_color = colors.HexColor("#ef4444")

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

    generated_date = datetime.now().strftime("%d %B %Y")

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20*mm,
        leftMargin=20*mm,
        topMargin=20*mm,
        bottomMargin=20*mm
    )

    dark_navy = colors.HexColor("#0f172a")
    mid_slate = colors.HexColor("#334155")
    light_slate = colors.HexColor("#64748b")
    very_light = colors.HexColor("#f8fafc")
    border_color = colors.HexColor("#e2e8f0")
    blue = colors.HexColor("#3b82f6")
    purple = colors.HexColor("#a855f7")

    styles = getSampleStyleSheet()

    label_style = ParagraphStyle("label",
        fontSize=8, fontName="Helvetica-Bold",
        textColor=light_slate, spaceAfter=4, leading=10)

    body_style = ParagraphStyle("body",
        fontSize=10, fontName="Helvetica",
        textColor=mid_slate, leading=16, spaceAfter=0)

    small_style = ParagraphStyle("small",
        fontSize=8, fontName="Helvetica",
        textColor=light_slate, leading=12)

    section_label_style = ParagraphStyle("section_label",
        fontSize=8, fontName="Helvetica-Bold",
        textColor=purple, spaceAfter=6, leading=10)

    elements = []

    # HEADER
    header_data = [[
        Paragraph('<font color="#0f172a"><b>West End </b></font><font color="#3b82f6"><b>Office Intelligence</b></font>',
            ParagraphStyle("h", fontSize=16, fontName="Helvetica-Bold")),
        Paragraph(f'<font color="#64748b">Generated: {generated_date}</font><br/><font color="#a855f7"><b>✦ Powered by Claude · Anthropic</b></font>',
            ParagraphStyle("hr", fontSize=9, fontName="Helvetica", alignment=TA_RIGHT, leading=14))
    ]]
    header_table = Table(header_data, colWidths=[110*mm, 60*mm])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
    ]))
    elements.append(header_table)
    elements.append(HRFlowable(width="100%", thickness=1.5, color=dark_navy, spaceAfter=16))

    # TITLE ROW
    title_data = [[
        Paragraph(f'<b>{area}</b>',
            ParagraphStyle("at", fontSize=26, fontName="Helvetica-Bold", textColor=dark_navy)),
        Paragraph(f'<b>{signal_text}</b>',
            ParagraphStyle("sig", fontSize=11, fontName="Helvetica-Bold", textColor=signal_color, alignment=TA_RIGHT))
    ]]
    title_table = Table(title_data, colWidths=[110*mm, 60*mm])
    title_table.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("BOTTOMPADDING", (0,0), (-1,-1), 2)]))
    elements.append(title_table)
    elements.append(Paragraph(
        f'Submarket Research Note · {int(first["year"])} {first["quarter"]} — {int(latest["year"])} {latest["quarter"]}',
        ParagraphStyle("subtitle", fontSize=10, fontName="Helvetica", textColor=light_slate, spaceAfter=0)
    ))
    elements.append(Spacer(1, 14))

    # KPI ROW
    kpi_data = [
        [Paragraph("PRIME RENT", label_style), Paragraph("FORECAST VACANCY", label_style),
         Paragraph("LATEST TAKE-UP", label_style), Paragraph("MARKET HEALTH", label_style), Paragraph("SENTIMENT", label_style)],
        [Paragraph(f'<b>£{float(latest["rent_psf"]):.0f}</b>', ParagraphStyle("kv", fontSize=20, fontName="Helvetica-Bold", textColor=dark_navy)),
         Paragraph(f'<b>{avg_vacancy:.1f}%</b>', ParagraphStyle("kv", fontSize=20, fontName="Helvetica-Bold", textColor=dark_navy)),
         Paragraph(f'<b>{latest_takeup:,}</b>', ParagraphStyle("kv", fontSize=20, fontName="Helvetica-Bold", textColor=dark_navy)),
         Paragraph(f'<b>{score}/100</b>', ParagraphStyle("kv", fontSize=20, fontName="Helvetica-Bold", textColor=dark_navy)),
         Paragraph(f'<b>{sentiment}</b>', ParagraphStyle("kv", fontSize=16, fontName="Helvetica-Bold", textColor=dark_navy))],
        [Paragraph("£ per sq ft", small_style), Paragraph("AI-predicted avg", small_style),
         Paragraph("sq ft leased", small_style), Paragraph("AI-derived score", small_style), Paragraph("Latest quarter", small_style)]
    ]

    kpi_table = Table(kpi_data, colWidths=[34*mm]*5, rowHeights=[14, 22, 12])
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), very_light),
        ("BOX", (0,0), (0,-1), 0.5, border_color),
        ("BOX", (1,0), (1,-1), 0.5, border_color),
        ("BOX", (2,0), (2,-1), 0.5, border_color),
        ("BOX", (3,0), (3,-1), 0.5, border_color),
        ("BOX", (4,0), (4,-1), 0.5, border_color),
        ("LEFTPADDING", (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 8),
        ("TOPPADDING", (0,0), (-1,0), 8),
        ("BOTTOMPADDING", (0,-1), (-1,-1), 8),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ]))
    elements.append(kpi_table)
    elements.append(Spacer(1, 16))

    # COMMENTARY
    elements.append(Paragraph("✦  AI MARKET COMMENTARY · CLAUDE", section_label_style))
    commentary_box = Table([[Paragraph(commentary_text, body_style)]], colWidths=[170*mm])
    commentary_box.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), very_light),
        ("LEFTPADDING", (0,0), (-1,-1), 12),
        ("RIGHTPADDING", (0,0), (-1,-1), 12),
        ("TOPPADDING", (0,0), (-1,-1), 12),
        ("BOTTOMPADDING", (0,0), (-1,-1), 12),
        ("LINEBEFORE", (0,0), (0,-1), 3, purple),
    ]))
    elements.append(commentary_box)
    elements.append(Spacer(1, 16))

    # DATA TABLE
    elements.append(Paragraph("QUARTERLY DATA BREAKDOWN", section_label_style))
    table_header = ["Period", "Prime Rent", "Vacancy", "Forecast", "Take-Up", "Sentiment"]
    table_rows_data = [table_header]
    for _, row in area_data.iterrows():
        table_rows_data.append([
            f"{int(row['year'])} {row['quarter']}",
            f"£{row['rent_psf']}",
            f"{row['vacancy_rate']:.1f}%",
            f"{row['predicted']:.2f}%",
            f"{int(row['takeup_sqft']):,}",
            str(row['sentiment'])
        ])

    data_table = Table(table_rows_data, colWidths=[28*mm, 28*mm, 26*mm, 26*mm, 30*mm, 32*mm])
    data_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), dark_navy),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,0), 8),
        ("FONTSIZE", (0,1), (-1,-1), 9),
        ("FONTNAME", (0,1), (-1,-1), "Helvetica"),
        ("TEXTCOLOR", (0,1), (-1,-1), mid_slate),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, very_light]),
        ("GRID", (0,0), (-1,-1), 0.3, border_color),
        ("LEFTPADDING", (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 8),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ]))
    elements.append(data_table)
    elements.append(Spacer(1, 20))

    # FOOTER
    elements.append(HRFlowable(width="100%", thickness=0.5, color=border_color, spaceAfter=10))
    footer_data = [[
        Paragraph(f'<b>West End Office Intelligence Platform</b><br/><font color="#94a3b8">Built by Dominic Mayne · Confidential Research Note · © {datetime.now().year}</font>',
            ParagraphStyle("fl", fontSize=8, fontName="Helvetica", textColor=mid_slate, leading=12)),
        Paragraph(f'<font color="#a855f7"><b>✦ Powered by Claude · Anthropic</b></font><br/><font color="#94a3b8">AI-Assisted Analytics</font>',
            ParagraphStyle("fr", fontSize=8, fontName="Helvetica", alignment=TA_RIGHT, leading=12))
    ]]
    footer_table = Table(footer_data, colWidths=[110*mm, 60*mm])
    footer_table.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP")]))
    elements.append(footer_table)
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(
        "This report has been generated using AI-assisted analytics and should be used for informational purposes only. Data sources include published market reports from Savills, CBRE, Colliers, BNP Paribas Real Estate and Avison Young. West End Office Intelligence Platform accepts no liability for decisions made based on this report.",
        ParagraphStyle("disc", fontSize=7, fontName="Helvetica", textColor=colors.HexColor("#cbd5e1"), leading=10)
    ))

    try:
        doc.build(elements)
        pdf_bytes = buffer.getvalue()
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