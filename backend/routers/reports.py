from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db, Competitor
from io import BytesIO
from fastapi.responses import StreamingResponse
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from datetime import datetime
import os

router = APIRouter(
    prefix="/api/reports",
    tags=["reports"]
)

def create_header(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(colors.HexColor('#0D3B66'))
    canvas.rect(0, 10*inch, 8.5*inch, 1*inch, fill=1, stroke=0)
    
    canvas.setFont('Helvetica-Bold', 16)
    canvas.setFillColor(colors.white)
    canvas.drawString(0.5*inch, 10.4*inch, "CERTIFY INTEL")
    
    canvas.setFont('Helvetica', 10)
    canvas.drawRightString(8*inch, 10.4*inch, f"Generated: {datetime.now().strftime('%Y-%m-%d')}")
    canvas.restoreState()

@router.get("/executive-summary")
def generate_executive_pdf(db: Session = Depends(get_db)):
    competitors = db.query(Competitor).all()
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=1.5*inch)
    
    elements = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#0D3B66'),
        spaceAfter=20
    )
    
    elements.append(Paragraph("Executive Intelligence Summary", title_style))
    elements.append(Spacer(1, 12))
    
    # Helper to parse numbers
    def parse_number(s):
        if not s: return 0
        import re
        # Remove currency symbols, commas, plus signs
        s_clean = re.sub(r'[^\d.]', '', str(s))
        if not s_clean: return 0
        try:
            return float(s_clean)
        except ValueError:
            return 0

    # Summary Statistics
    total_comps = len(competitors)
    avg_customers = 0
    avg_price = 0
    
    if total_comps > 0:
        total_customers = sum(parse_number(c.customer_count) for c in competitors)
        avg_customers = int(total_customers / total_comps)
        
        total_price = sum(parse_number(c.base_price) for c in competitors)
        avg_price = int(total_price / total_comps)

    stats_data = [
        ['Total Competitors', 'Avg Customer Count', 'Avg Base Price'],
        [total_comps, 
         f"{avg_customers:,}", 
         f"${avg_price}"]
    ]
    
    t = Table(stats_data, colWidths=[2.5*inch, 2.5*inch, 2.5*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#e2e8f0')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#1e293b')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 12),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('BACKGROUND', (0,1), (-1,-1), colors.white),
        ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1'))
    ]))
    elements.append(t)
    elements.append(Spacer(1, 30))
    
    # Top Competitors
    elements.append(Paragraph("Top Competitors by Market Presence", styles['Heading2']))
    # Sort by parsed customer count
    top_competitors = sorted(competitors, key=lambda x: parse_number(x.customer_count), reverse=True)[:10]
    
    comp_data = [['Competitor', 'Customers', 'Price', 'G2 Rating']]
    for c in top_competitors:
        # Use values mostly as-is since they are strings, but could clean them if needed
        comp_data.append([
            c.name,
            c.customer_count if c.customer_count else "N/A",
            c.base_price if c.base_price else "N/A",
            str(c.g2_rating) if c.g2_rating else "N/A"
        ])
        
    t2 = Table(comp_data, colWidths=[3*inch, 1.5*inch, 1.5*inch, 1*inch])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0D3B66')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('GRID', (0,0), (-1,-1), 1, colors.gray),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.whitesmoke])
    ]))
    elements.append(t2)
    
    doc.build(elements, onFirstPage=create_header, onLaterPages=create_header)
    buffer.seek(0)
    
    return StreamingResponse(
        buffer, 
        media_type="application/pdf", 
        headers={"Content-Disposition": f"attachment; filename=Certify_Intel_Summary_{datetime.now().strftime('%Y%m%d')}.pdf"}
    )
