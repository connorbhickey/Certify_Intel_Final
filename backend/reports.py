"""
Certify Intel - Report Generator (v5.0.7)
PDF executive briefings, battlecards, and comparison reports

v5.0.7: Added dimension-aware battlecard generation with Sales & Marketing module integration.
"""
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from io import BytesIO

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
    from reportlab.graphics.shapes import Drawing, Rect
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics.charts.piecharts import Pie
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    print("Warning: reportlab not installed. Run: pip install reportlab")

# v5.0.7: Import battlecard generator for dynamic battlecards
try:
    from battlecard_generator import BattlecardGenerator as DynamicBattlecardGenerator, BATTLECARD_TEMPLATES
    DYNAMIC_BATTLECARD_AVAILABLE = True
except ImportError:
    DYNAMIC_BATTLECARD_AVAILABLE = False
    print("Dynamic battlecard generator not available")

# v5.0.7: Import dimension metadata
try:
    from sales_marketing_module import DIMENSION_METADATA, DimensionID, SCORE_LABELS
    DIMENSION_METADATA_AVAILABLE = True
except ImportError:
    DIMENSION_METADATA_AVAILABLE = False
    print("Dimension metadata not available")


# ============== Executive Briefing PDF ==============

class ExecutiveBriefingGenerator:
    """Generates weekly executive briefing PDFs."""
    
    def __init__(self):
        self.styles = getSampleStyleSheet() if REPORTLAB_AVAILABLE else None
        self._setup_styles()
    
    def _setup_styles(self):
        """Set up custom paragraph styles."""
        if not REPORTLAB_AVAILABLE:
            return
        
        self.styles.add(ParagraphStyle(
            name='Heading1Custom',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1B2B65'),
            spaceAfter=20
        ))
        
        self.styles.add(ParagraphStyle(
            name='Heading2Custom',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#1B2B65'),
            spaceBefore=15,
            spaceAfter=10
        ))
        
        self.styles.add(ParagraphStyle(
            name='BodyCustom',
            parent=self.styles['Normal'],
            fontSize=11,
            leading=14
        ))
        
        self.styles.add(ParagraphStyle(
            name='ThreatMedium',
            parent=self.styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor('#FFC107')
        ))
        
        if 'Heading3' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='Heading3',
                parent=self.styles['Heading2'],
                fontSize=12,
                textColor=colors.HexColor('#1B2B65'),
                spaceBefore=10,
                spaceAfter=5
            ))
    
    def generate_briefing(
        self,
        competitors: List[Dict[str, Any]],
        changes: List[Dict[str, Any]],
        stats: Dict[str, Any],
        output_path: str
    ) -> str:
        """Generate executive briefing PDF."""
        if not REPORTLAB_AVAILABLE:
            return self._generate_text_briefing(competitors, changes, stats, output_path)
        
        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        story = []
        
        # Title
        story.append(Paragraph(
            "Certify Intel Executive Briefing",
            self.styles['Heading1Custom']
        ))
        story.append(Paragraph(
            f"Week of {datetime.now().strftime('%B %d, %Y')}",
            self.styles['BodyCustom']
        ))
        story.append(Spacer(1, 20))
        
        # Executive Summary
        story.append(Paragraph("Executive Summary", self.styles['Heading2Custom']))
        summary = f"""
        This week's competitive intelligence update covers {stats.get('total_competitors', 0)} competitors 
        in the patient intake and engagement market. We detected {len(changes)} changes across the 
        competitive landscape, with {stats.get('high_threat', 0)} high-threat competitors requiring 
        close monitoring.
        """
        story.append(Paragraph(summary, self.styles['BodyCustom']))
        story.append(Spacer(1, 15))
        
        # Key Metrics Table
        story.append(Paragraph("Key Metrics", self.styles['Heading2Custom']))
        metrics_data = [
            ['Metric', 'Value'],
            ['Total Competitors', str(stats.get('total_competitors', 0))],
            ['High Threat', str(stats.get('high_threat', 0))],
            ['Medium Threat', str(stats.get('medium_threat', 0))],
            ['Low Threat', str(stats.get('low_threat', 0))],
            ['Changes This Week', str(len(changes))],
        ]
        
        metrics_table = Table(metrics_data, colWidths=[3*inch, 2*inch])
        metrics_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1B2B65')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(metrics_table)
        story.append(Spacer(1, 20))
        
        # High Priority Changes
        high_changes = [c for c in changes if c.get('severity') == 'High']
        if high_changes:
            story.append(Paragraph("🚨 High Priority Changes", self.styles['Heading2Custom']))
            for change in high_changes[:5]:
                text = f"<b>{change.get('competitor_name')}</b>: {change.get('change_type')} changed from '{change.get('previous_value', 'N/A')}' to '{change.get('new_value')}'"
                story.append(Paragraph(text, self.styles['ThreatHigh']))
                story.append(Spacer(1, 5))
            story.append(Spacer(1, 15))
        
        # Top Threats Overview
        story.append(Paragraph("Top Competitive Threats", self.styles['Heading2Custom']))
        high_threat_comps = [c for c in competitors if c.get('threat_level', '').upper() == 'HIGH']
        
        for comp in high_threat_comps[:3]:
            name = comp.get('name', 'Unknown')
            customers = comp.get('customer_count', 'Unknown')
            funding = comp.get('funding_total', 'Unknown')
            products = comp.get('product_categories', 'Unknown')
            
            text = f"""
            <b>{name}</b><br/>
            Customers: {customers} | Funding: {funding}<br/>
            Products: {products}
            """
            story.append(Paragraph(text, self.styles['BodyCustom']))
            story.append(Spacer(1, 10))
        
        # Recommendations - dynamically generated from actual top-threat competitors
        story.append(Paragraph("Recommendations", self.styles['Heading2Custom']))
        top_threat_names = [c.get('name', 'Unknown') for c in high_threat_comps[:3]]
        recommendations = []
        if top_threat_names:
            recommendations.append(
                f"Monitor {top_threat_names[0]}'s AI initiatives for potential feature parity considerations"
            )
        recommendations.append("Evaluate pricing strategy against low-cost entrants in SMB segment")
        recommendations.append("Track job postings from high-growth competitors for talent competition")
        recommendations.append("Review integration partnerships that competitors are announcing")
        if len(top_threat_names) >= 2:
            recommendations.append(
                f"Conduct deep-dive analysis on {' and '.join(top_threat_names[:2])} product roadmaps"
            )
        for rec in recommendations:
            story.append(Paragraph(f"&bull; {rec}", self.styles['BodyCustom']))
        
        # Build PDF
        doc.build(story)
        
        return output_path
    
    def _generate_text_briefing(
        self,
        competitors: List[Dict],
        changes: List[Dict],
        stats: Dict,
        output_path: str
    ) -> str:
        """Generate text-based briefing when ReportLab not available."""
        text_path = output_path.replace('.pdf', '.txt')
        
        content = f"""
CERTIFY INTEL EXECUTIVE BRIEFING
Week of {datetime.now().strftime('%B %d, %Y')}

EXECUTIVE SUMMARY
-----------------
This week's competitive intelligence update covers {stats.get('total_competitors', 0)} competitors.
We detected {len(changes)} changes across the competitive landscape.
High-threat competitors: {stats.get('high_threat', 0)}

KEY METRICS
-----------
Total Competitors: {stats.get('total_competitors', 0)}
High Threat: {stats.get('high_threat', 0)}
Medium Threat: {stats.get('medium_threat', 0)}
Low Threat: {stats.get('low_threat', 0)}
Changes This Week: {len(changes)}

HIGH PRIORITY CHANGES
---------------------
"""
        for change in [c for c in changes if c.get('severity') == 'High'][:5]:
            content += f"- {change.get('competitor_name')}: {change.get('change_type')} changed to {change.get('new_value')}\n"
        
        with open(text_path, 'w') as f:
            f.write(content)
        
        return text_path


# ============== Battlecard Generator ==============

class BattlecardGenerator:
    """Generates sales battlecards for competitors."""
    
    def __init__(self):
        self.styles = getSampleStyleSheet() if REPORTLAB_AVAILABLE else None
    
    def generate_battlecard(
        self,
        competitor: Dict[str, Any],
        analysis: Dict[str, Any],
        output_path: str
    ) -> str:
        """Generate a single competitor battlecard PDF."""
        if not REPORTLAB_AVAILABLE:
            return self._generate_text_battlecard(competitor, analysis, output_path)
        
        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )
        
        story = []
        
        name = competitor.get('name', 'Unknown')
        
        # Header
        header_style = ParagraphStyle(
            name='BattlecardHeader',
            fontSize=20,
            textColor=colors.white,
            spaceAfter=10
        )
        
        # Competitor name with threat level color
        threat = competitor.get('threat_level', 'Medium')
        threat_color = {'High': '#DC3545', 'Medium': '#FFC107', 'Low': '#28A745'}.get(threat, '#6C757D')
        
        story.append(Paragraph(f"<font color='#1B2B65'><b>BATTLECARD: {name}</b></font>", self.styles['Heading1']))
        story.append(Paragraph(f"<font color='{threat_color}'>Threat Level: {threat}</font>", self.styles['Normal']))
        story.append(Spacer(1, 15))
        
        # Quick Facts
        story.append(Paragraph("<b>Quick Facts</b>", self.styles['Heading2']))
        facts_data = [
            ['Founded', competitor.get('year_founded', 'N/A')],
            ['Headquarters', competitor.get('headquarters', 'N/A')],
            ['Employees', competitor.get('employee_count', 'N/A')],
            ['Customers', competitor.get('customer_count', 'N/A')],
            ['Funding', competitor.get('funding_total', 'N/A')],
            ['Pricing', f"{competitor.get('pricing_model', '')} - {competitor.get('base_price', 'N/A')}"],
        ]
        
        facts_table = Table(facts_data, colWidths=[2*inch, 4*inch])
        facts_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#E8E8E8')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(facts_table)
        story.append(Spacer(1, 15))
        
        # Stock Market Data (If Public)
        stock_data = competitor.get('stock_data')
        if stock_data:
            story.append(Paragraph("<b>Stock Market Performance (Live)</b>", self.styles['Heading2']))
            
            # Helper for formatting numbers
            def fmt_num(val, prefix="", suffix=""):
                if val is None: return "N/A"
                if isinstance(val, (int, float)):
                    if "M" in suffix or "B" in suffix: return f"{prefix}{val}" # Already formatted
                    return f"{prefix}{val:,.2f}{suffix}"
                return str(val)

            change_color = '#28A745' if stock_data.get('change', 0) >= 0 else '#DC3545'
            
            stock_rows = [
                ['Price', fmt_num(stock_data.get('price'), "$")],
                ['Change', f"{fmt_num(stock_data.get('change'))} ({fmt_num(stock_data.get('change_percent'), '', '%')})"],
                ['Market Cap', fmt_num(stock_data.get('market_cap') / 1e9, "$", "B") if isinstance(stock_data.get('market_cap'), (int, float)) else "N/A"],
                ['P/E Ratio', fmt_num(stock_data.get('pe_ratio'))],
                ['EPS', fmt_num(stock_data.get('eps'))],
                ['Beta', fmt_num(stock_data.get('beta'))],
                ['52W High', fmt_num(stock_data.get('high52'), "$")],
                ['52W Low', fmt_num(stock_data.get('low52'), "$")]
            ]
            
            # 4x2 Grid
            data = [
                stock_rows[0] + stock_rows[1],
                stock_rows[2] + stock_rows[3],
                stock_rows[4] + stock_rows[5],
                stock_rows[6] + stock_rows[7]
            ]
            
            stock_table = Table(data, colWidths=[1.5*inch, 1.5*inch, 1.5*inch, 1.5*inch])
            stock_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
                ('TEXTCOLOR', (3, 0), (3, 0), colors.HexColor(change_color)), # Colorize Change
                ('PADDING', (0, 0), (-1, -1), 6),
            ]))
            story.append(stock_table)
            story.append(Spacer(1, 15))
        
        # Private Intelligence (Deep Dive) - If stocked data implies private or requested
        if 'deep_dive' in competitor:
            dd = competitor['deep_dive']
            story.append(Paragraph("<b>Private Intelligence (Deep Dive)</b>", self.styles['Heading2']))
            
            # Helper to safely get nested keys
            def get_val(cat, key, default='N/A'):
                return dd.get(cat, {}).get(key, default)

            # 1. Capital & Growth
            story.append(Paragraph("<b>Capital & Growth Signals</b>", self.styles['Heading3']))
            cap_rows = [
                ['Est. Revenue', get_val('capital', 'est_revenue')],
                ['Funding', get_val('capital', 'funding_total')],
                ['Employees', str(get_val('growth', 'headcount'))],
                ['6-Mo Growth', f"{get_val('growth', 'growth_rate')}%"],
                ['Open Roles', str(get_val('growth', 'active_hiring'))],
                ['Stage', get_val('capital', 'stage')]
            ]
            
            # Format as 3x2 grid
            cap_data = [
                cap_rows[0] + cap_rows[1],
                cap_rows[2] + cap_rows[3],
                cap_rows[4] + cap_rows[5]
            ]
            
            cap_table = Table(cap_data, colWidths=[1.2*inch, 1.5*inch, 1.2*inch, 1.5*inch])
            cap_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'), # Labels bold
                ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
                ('PADDING', (0, 0), (-1, -1), 5),
            ]))
            story.append(cap_table)
            story.append(Spacer(1, 10))

            # 2. Digital Footprint
            story.append(Paragraph("<b>Digital Footprint & Tech</b>", self.styles['Heading3']))
            dig_rows = [
                ['Google Ads', f"{get_val('digital', 'ads_active')} Creatives"],
                ['Brand Trend', f"{get_val('digital', 'brand_index')}/100 ({get_val('digital', 'trend')})"],
                ['Reviews', f"{get_val('digital', 'review_velocity')}/mo"],
                ['Tech Signal', get_val('digital', 'tech_signal')]
            ]
            dig_table = Table([dig_rows[0] + dig_rows[1], dig_rows[2] + dig_rows[3]], colWidths=[1.2*inch, 1.5*inch, 1.2*inch, 1.5*inch])
            dig_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
                ('PADDING', (0, 0), (-1, -1), 5),
            ]))
            story.append(dig_table)
            story.append(Spacer(1, 10))

            # 3. Sentiment & Risks
            story.append(Paragraph("<b>Sentiment, SEO & Risk</b>", self.styles['Heading3']))
            risk_rows = [
                ['G2 Score', f"{get_val('sentiment', 'g2_score')}/5"],
                ['Domain Auth', str(get_val('seo', 'da'))],
                ['Pedigree', get_val('risk', 'founder_exit')],
                ['Risk Flags', "⚠️ WARN" if get_val('risk', 'warn') else "None"]
            ]
            risk_table = Table([risk_rows[0] + risk_rows[1], risk_rows[2] + risk_rows[3]], colWidths=[1.2*inch, 1.5*inch, 1.2*inch, 1.5*inch])
            risk_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
                ('PADDING', (0, 0), (-1, -1), 5),
            ]))
            story.append(risk_table)
            story.append(Spacer(1, 15))
        
        # Products & Features
        story.append(Paragraph("<b>Products & Features</b>", self.styles['Heading2']))
        products = competitor.get('product_categories', 'N/A')
        features = competitor.get('key_features', 'N/A')
        story.append(Paragraph(f"<b>Products:</b> {products}", self.styles['Normal']))
        story.append(Paragraph(f"<b>Key Features:</b> {features}", self.styles['Normal']))
        story.append(Spacer(1, 15))
        
        # Strengths & Weaknesses
        if analysis:
            battlecard = analysis.get('battlecard', {})
            
            story.append(Paragraph("<b>Strengths</b>", self.styles['Heading2']))
            story.append(Paragraph(battlecard.get('strengths', 'N/A'), self.styles['Normal']))
            
            story.append(Paragraph("<b>Weaknesses</b>", self.styles['Heading2']))
            story.append(Paragraph(battlecard.get('weaknesses', 'N/A'), self.styles['Normal']))
            
            story.append(Paragraph("<b>Key Differentiators</b>", self.styles['Heading2']))
            story.append(Paragraph(battlecard.get('key_differentiators', 'N/A'), self.styles['Normal']))
        
        story.append(Spacer(1, 15))
        
        # Win Against Tactics
        story.append(Paragraph("<b>How to Win Against Them</b>", self.styles['Heading2']))
        tactics = self._generate_win_tactics(competitor)
        for tactic in tactics:
            story.append(Paragraph(f"• {tactic}", self.styles['Normal']))
        
        story.append(Spacer(1, 15))
        
        # Common Objections
        story.append(Paragraph("<b>Handling Common Objections</b>", self.styles['Heading2']))
        objections = self._generate_objection_handlers(competitor)
        for obj, response in objections:
            story.append(Paragraph(f"<b>Q:</b> {obj}", self.styles['Normal']))
            story.append(Paragraph(f"<b>A:</b> {response}", self.styles['Normal']))
            story.append(Spacer(1, 5))
        
        # Build PDF
        doc.build(story)
        
        return output_path
    
    def _generate_win_tactics(self, competitor: Dict) -> List[str]:
        """Generate tactics to win against this competitor."""
        tactics = []
        
        size = (competitor.get('customer_size_focus') or '').lower()
        if 'large' in size or 'enterprise' in size:
            tactics.append("Emphasize our agility and faster implementation times")
            tactics.append("Highlight total cost of ownership vs enterprise overhead")
        
        if 'public' in (competitor.get('latest_round') or '').lower():
            tactics.append("Stress our focus and dedication as a private company")
            tactics.append("Note their obligation to shareholders may impact customer service")
        
        pricing = competitor.get('pricing_model', '').lower()
        if 'visit' in pricing:
            tactics.append("Compare our predictable pricing model vs variable costs")
        
        tactics.append("Focus on our integration depth with their specific EHR")
        tactics.append("Offer a pilot or proof of concept to demonstrate value")
        
        return tactics
    
    def _generate_objection_handlers(self, competitor: Dict) -> List[tuple]:
        """Generate common objections and handlers."""
        name = competitor.get('name', 'Competitor')
        
        return [
            (f"Why shouldn't we go with {name}?", 
             f"While {name} is a strong player, our solution offers [specific advantage] that better aligns with your needs."),
            (f"{name} has more customers than you.",
             "Size isn't everything. Our focused approach means you get dedicated attention and faster innovation."),
            (f"{name} is publicly traded, so they're more stable.",
             "Public companies face quarterly pressures. We're built for long-term customer success."),
        ]
    
    def _generate_text_battlecard(self, competitor: Dict, analysis: Dict, output_path: str) -> str:
        """Text-based battlecard when ReportLab not available."""
        text_path = output_path.replace('.pdf', '.txt')
        
        name = competitor.get('name', 'Unknown')
        content = f"""
BATTLECARD: {name}
==================

THREAT LEVEL: {competitor.get('threat_level', 'Unknown')}

QUICK FACTS
-----------
Founded: {competitor.get('year_founded', 'N/A')}
Headquarters: {competitor.get('headquarters', 'N/A')}
Employees: {competitor.get('employee_count', 'N/A')}
Customers: {competitor.get('customer_count', 'N/A')}
Funding: {competitor.get('funding_total', 'N/A')}
Pricing: {competitor.get('pricing_model', '')} - {competitor.get('base_price', 'N/A')}

PRODUCTS
--------
{competitor.get('product_categories', 'N/A')}

KEY FEATURES
------------
{competitor.get('key_features', 'N/A')}
"""
        
        with open(text_path, 'w') as f:
            f.write(content)
        
        return text_path
    
    def generate_all_battlecards(
        self,
        competitors: List[Dict[str, Any]],
        output_dir: str
    ) -> List[str]:
        """Generate battlecards for all competitors."""
        os.makedirs(output_dir, exist_ok=True)
        
        paths = []
        for comp in competitors:
            name = comp.get('name', 'unknown').replace(' ', '_').lower()
            path = os.path.join(output_dir, f"battlecard_{name}.pdf")
            self.generate_battlecard(comp, {}, path)
            paths.append(path)
        
        return paths


# ============== Comparison Report Generator ==============

class ComparisonReportGenerator:
    """Generates side-by-side competitor comparison reports."""
    
    def __init__(self):
        self.styles = getSampleStyleSheet() if REPORTLAB_AVAILABLE else None
    
    def generate_comparison(
        self,
        competitors: List[Dict[str, Any]],
        output_path: str
    ) -> str:
        """Generate a multi-competitor comparison PDF."""
        if not REPORTLAB_AVAILABLE:
            return self._generate_text_comparison(competitors, output_path)
        
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )
        
        story = []
        
        # Title
        story.append(Paragraph("Competitive Comparison Report", self.styles['Heading1']))
        story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y')}", self.styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Build comparison table
        headers = ['Attribute'] + [c.get('name', 'Unknown')[:15] for c in competitors[:5]]
        
        attributes = [
            ('Threat Level', 'threat_level'),
            ('Pricing Model', 'pricing_model'),
            ('Base Price', 'base_price'),
            ('Products', 'product_categories'),
            ('Customer Count', 'customer_count'),
            ('G2 Rating', 'g2_rating'),
            ('Employees', 'employee_count'),
            ('Target Segment', 'target_segments'),
            ('Funding', 'funding_total'),
            # New Deep Dive Columns
            ('Google Ads', 'ads_count'),
            ('Brand Index', 'brand_index'),
            ('Domain Auth', 'domain_auth'),
        ]
        
        data = [headers]
        for attr_name, attr_key in attributes:
            row = [attr_name]
            for comp in competitors[:5]:
                # Handle Deep Dive data if present, otherwise fallback to top-level key
                value = 'N/A'
                if 'deep_dive' in comp:
                    dd = comp['deep_dive']
                    if attr_key == 'ads_count': value = dd.get('digital', {}).get('ads_active')
                    elif attr_key == 'brand_index': value = dd.get('digital', {}).get('brand_index')
                    elif attr_key == 'domain_auth': value = dd.get('seo', {}).get('da')
                    else: value = comp.get(attr_key, 'N/A')
                else:
                    value = comp.get(attr_key, 'N/A')
                
                if value and len(str(value)) > 20:
                    value = str(value)[:20] + '...'
                row.append(str(value) if value is not None else 'N/A')
            data.append(row)
        
        # Create table
        col_width = 1.3 * inch
        table = Table(data, colWidths=[1.5*inch] + [col_width]*(len(headers)-1))
        
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1B2B65')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#E8E8E8')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 4),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        story.append(table)
        
        # Build PDF
        doc.build(story)
        
        return output_path
    
    def _generate_text_comparison(self, competitors: List[Dict], output_path: str) -> str:
        """Text-based comparison when ReportLab not available."""
        text_path = output_path.replace('.pdf', '.txt')
        
        content = "COMPETITIVE COMPARISON REPORT\n"
        content += "=" * 50 + "\n\n"
        
        for comp in competitors:
            content += f"{comp.get('name', 'Unknown')}\n"
            content += "-" * 30 + "\n"
            content += f"Threat: {comp.get('threat_level', 'N/A')}\n"
            content += f"Pricing: {comp.get('base_price', 'N/A')}\n"
            content += f"Customers: {comp.get('customer_count', 'N/A')}\n\n"
        
        with open(text_path, 'w') as f:
            f.write(content)
        
        return text_path


# ============== Dimension Battlecard Generator (v5.0.7) ==============

class DimensionBattlecardPDFGenerator:
    """
    v5.0.7: Generates dimension-aware battlecard PDFs.
    Integrates with Sales & Marketing module for dimension scores.
    """

    def __init__(self):
        self.styles = getSampleStyleSheet() if REPORTLAB_AVAILABLE else None
        self._setup_styles()

        # Score colors (1-5)
        self.score_colors = {
            1: colors.HexColor('#DC3545'),  # Red - Major Weakness
            2: colors.HexColor('#FD7E14'),  # Orange - Weakness
            3: colors.HexColor('#FFC107'),  # Yellow - Neutral
            4: colors.HexColor('#28A745'),  # Green - Strength
            5: colors.HexColor('#20C997'),  # Teal - Major Strength
        }

    def _setup_styles(self):
        """Set up custom paragraph styles for dimension battlecards."""
        if not REPORTLAB_AVAILABLE:
            return

        if 'DimensionHeader' not in [s.name for s in self.styles.byName.values()]:
            self.styles.add(ParagraphStyle(
                name='DimensionHeader',
                parent=self.styles['Heading2'],
                fontSize=14,
                textColor=colors.HexColor('#1B2B65'),
                spaceBefore=15,
                spaceAfter=8
            ))

            self.styles.add(ParagraphStyle(
                name='DimensionName',
                parent=self.styles['Normal'],
                fontSize=10,
                textColor=colors.HexColor('#333333'),
                spaceBefore=4,
                spaceAfter=2
            ))

            self.styles.add(ParagraphStyle(
                name='Evidence',
                parent=self.styles['Normal'],
                fontSize=9,
                textColor=colors.HexColor('#666666'),
                leftIndent=10
            ))

    def generate_dimension_battlecard(
        self,
        competitor: Dict[str, Any],
        dimension_profile: Dict[str, Any],
        battlecard_content: Dict[str, Any],
        output_path: str
    ) -> str:
        """
        Generate a dimension-aware battlecard PDF.

        Args:
            competitor: Competitor data dict
            dimension_profile: Dict with dimension scores and evidence
            battlecard_content: Generated battlecard content from BattlecardGenerator
            output_path: Path to save the PDF

        Returns:
            Path to generated PDF
        """
        if not REPORTLAB_AVAILABLE:
            return self._generate_text_dimension_battlecard(
                competitor, dimension_profile, battlecard_content, output_path
            )

        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        story = []
        name = competitor.get('name', 'Unknown')

        # Header
        story.append(Paragraph(
            f"<font color='#1B2B65'><b>DIMENSION BATTLECARD: {name}</b></font>",
            self.styles['Heading1']
        ))

        # Threat level
        threat = competitor.get('threat_level', 'Medium')
        threat_color = {'High': '#DC3545', 'Medium': '#FFC107', 'Low': '#28A745'}.get(threat, '#6C757D')
        story.append(Paragraph(
            f"<font color='{threat_color}'>Threat Level: {threat}</font>",
            self.styles['Normal']
        ))

        # Overall dimension score
        overall_score = dimension_profile.get('overall_score')
        if overall_score:
            story.append(Paragraph(
                f"<b>Overall Dimension Score:</b> {overall_score:.1f}/5",
                self.styles['Normal']
            ))

        story.append(Spacer(1, 15))

        # Dimension Scorecard Section
        story.append(Paragraph("📊 Competitive Dimension Scorecard", self.styles['DimensionHeader']))

        # Build dimension scorecard table
        dimensions = dimension_profile.get('dimensions', {})
        if dimensions:
            scorecard_data = [['Dimension', 'Score', 'Assessment']]

            for dim_id, dim_data in dimensions.items():
                score = dim_data.get('score', 0)
                dim_name = dim_data.get('name', dim_id)

                # Score label
                score_label = SCORE_LABELS.get(score, 'Unknown') if DIMENSION_METADATA_AVAILABLE else str(score)

                scorecard_data.append([
                    dim_name[:30],
                    str(score) if score else 'N/A',
                    score_label
                ])

            scorecard_table = Table(scorecard_data, colWidths=[2.5*inch, 0.8*inch, 2*inch])

            # Style the table with score colors
            table_style = [
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1B2B65')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('PADDING', (0, 0), (-1, -1), 6),
                ('ALIGN', (1, 1), (1, -1), 'CENTER'),
            ]

            # Color code score cells
            for i, (dim_id, dim_data) in enumerate(dimensions.items(), start=1):
                score = dim_data.get('score', 0)
                if score in self.score_colors:
                    table_style.append(('BACKGROUND', (1, i), (1, i), self.score_colors[score]))
                    table_style.append(('TEXTCOLOR', (1, i), (1, i), colors.white))

            scorecard_table.setStyle(TableStyle(table_style))
            story.append(scorecard_table)
        else:
            story.append(Paragraph("<i>No dimension scores available</i>", self.styles['Normal']))

        story.append(Spacer(1, 15))

        # Key Evidence Section
        story.append(Paragraph("📋 Key Evidence by Dimension", self.styles['DimensionHeader']))

        for dim_id, dim_data in dimensions.items():
            evidence = dim_data.get('evidence')
            if evidence:
                dim_name = dim_data.get('name', dim_id)
                story.append(Paragraph(f"<b>{dim_name}:</b>", self.styles['DimensionName']))
                story.append(Paragraph(evidence[:300] + ('...' if len(evidence) > 300 else ''), self.styles['Evidence']))
                story.append(Spacer(1, 5))

        story.append(Spacer(1, 15))

        # Battlecard Content Sections
        if battlecard_content:
            sections = battlecard_content.get('sections', [])

            for section in sections:
                section_title = section.get('title', '')
                section_content = section.get('content', '')

                if section_title:
                    story.append(Paragraph(f"<b>{section_title}</b>", self.styles['Heading2']))

                if section_content:
                    # Handle bullet points
                    if isinstance(section_content, list):
                        for item in section_content[:10]:
                            story.append(Paragraph(f"• {item}", self.styles['Normal']))
                    else:
                        story.append(Paragraph(section_content, self.styles['Normal']))

                story.append(Spacer(1, 10))

        # Build PDF
        doc.build(story)
        return output_path

    def _generate_text_dimension_battlecard(
        self,
        competitor: Dict,
        dimension_profile: Dict,
        battlecard_content: Dict,
        output_path: str
    ) -> str:
        """Text-based battlecard when ReportLab not available."""
        text_path = output_path.replace('.pdf', '.txt')

        name = competitor.get('name', 'Unknown')
        content = f"""
DIMENSION BATTLECARD: {name}
{'=' * 50}

THREAT LEVEL: {competitor.get('threat_level', 'Unknown')}
OVERALL DIMENSION SCORE: {dimension_profile.get('overall_score', 'N/A')}

COMPETITIVE DIMENSION SCORECARD
{'-' * 30}
"""
        dimensions = dimension_profile.get('dimensions', {})
        for dim_id, dim_data in dimensions.items():
            score = dim_data.get('score', 'N/A')
            dim_name = dim_data.get('name', dim_id)
            content += f"{dim_name}: {score}/5\n"

        content += f"""
KEY EVIDENCE
{'-' * 30}
"""
        for dim_id, dim_data in dimensions.items():
            evidence = dim_data.get('evidence')
            if evidence:
                content += f"\n{dim_data.get('name', dim_id)}:\n{evidence[:200]}...\n"

        with open(text_path, 'w') as f:
            f.write(content)

        return text_path


# ============== Report Manager ==============

class ReportManager:
    """Manages all report generation."""

    def __init__(self, output_dir: str = "./reports"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

        self.briefing_gen = ExecutiveBriefingGenerator()
        self.battlecard_gen = BattlecardGenerator()
        self.comparison_gen = ComparisonReportGenerator()
        self.dimension_battlecard_gen = DimensionBattlecardPDFGenerator()  # v5.0.7
    
    def generate_weekly_briefing(
        self,
        competitors: List[Dict],
        changes: List[Dict],
        stats: Dict
    ) -> str:
        """Generate weekly executive briefing."""
        path = os.path.join(
            self.output_dir, 
            f"executive_briefing_{datetime.now().strftime('%Y%m%d')}.pdf"
        )
        return self.briefing_gen.generate_briefing(competitors, changes, stats, path)
    
    def generate_battlecard(self, competitor: Dict, analysis: Dict = None) -> str:
        """Generate single competitor battlecard."""
        name = competitor.get('name', 'unknown').replace(' ', '_').lower()
        path = os.path.join(self.output_dir, f"battlecard_{name}.pdf")
        return self.battlecard_gen.generate_battlecard(competitor, analysis or {}, path)
    
    def generate_all_battlecards(self, competitors: List[Dict]) -> List[str]:
        """Generate battlecards for all competitors."""
        battlecards_dir = os.path.join(self.output_dir, "battlecards")
        return self.battlecard_gen.generate_all_battlecards(competitors, battlecards_dir)
    
    def generate_comparison(self, competitors: List[Dict]) -> str:
        """Generate comparison report."""
        path = os.path.join(
            self.output_dir,
            f"comparison_report_{datetime.now().strftime('%Y%m%d')}.pdf"
        )
        return self.comparison_gen.generate_comparison(competitors, path)

    def generate_dimension_battlecard(
        self,
        competitor: Dict,
        dimension_profile: Dict,
        battlecard_content: Dict = None
    ) -> str:
        """
        v5.0.7: Generate dimension-aware battlecard PDF.

        Args:
            competitor: Competitor data dict
            dimension_profile: Dict with dimension scores and evidence
            battlecard_content: Optional generated battlecard content

        Returns:
            Path to generated PDF
        """
        name = competitor.get('name', 'unknown').replace(' ', '_').lower()
        path = os.path.join(self.output_dir, f"dimension_battlecard_{name}.pdf")
        return self.dimension_battlecard_gen.generate_dimension_battlecard(
            competitor, dimension_profile, battlecard_content or {}, path
        )

    def generate_dimension_battlecard_from_db(
        self,
        competitor_id: int,
        db_session,
        battlecard_type: str = "full"
    ) -> str:
        """
        v5.0.7: Generate dimension battlecard from database data.

        Args:
            competitor_id: ID of the competitor
            db_session: SQLAlchemy database session
            battlecard_type: Type of battlecard (full, quick, objection_handler)

        Returns:
            Path to generated PDF
        """
        from database import Competitor

        # Get competitor from database
        competitor = db_session.query(Competitor).filter(
            Competitor.id == competitor_id
        ).first()

        if not competitor:
            raise ValueError(f"Competitor {competitor_id} not found")

        # Build competitor dict
        competitor_dict = {
            "id": competitor.id,
            "name": competitor.name,
            "threat_level": competitor.threat_level,
            "website": competitor.website,
            "year_founded": competitor.year_founded,
            "headquarters": competitor.headquarters,
            "employee_count": competitor.employee_count,
            "customer_count": competitor.customer_count,
            "funding_total": competitor.funding_total,
            "pricing_model": competitor.pricing_model,
            "base_price": competitor.base_price,
            "product_categories": competitor.product_categories,
            "key_features": competitor.key_features,
        }

        # Build dimension profile from competitor fields
        dimension_profile = self._build_dimension_profile_from_competitor(competitor)

        # Generate battlecard content if dynamic generator available
        battlecard_content = {}
        if DYNAMIC_BATTLECARD_AVAILABLE:
            try:
                gen = DynamicBattlecardGenerator(db_session)
                result = gen.generate_battlecard(
                    competitor_id=competitor_id,
                    battlecard_type=battlecard_type
                )
                battlecard_content = result
            except Exception as e:
                print(f"Error generating dynamic battlecard: {e}")

        return self.generate_dimension_battlecard(
            competitor_dict, dimension_profile, battlecard_content
        )

    def _build_dimension_profile_from_competitor(self, competitor) -> Dict[str, Any]:
        """
        v5.0.7: Build dimension profile dict from Competitor model.

        Args:
            competitor: Competitor SQLAlchemy model instance

        Returns:
            Dict with dimension scores and evidence
        """
        dimensions = {}
        total_score = 0
        scored_count = 0

        # Dimension field mappings
        dimension_fields = [
            ("product_packaging", "Product Modules & Packaging"),
            ("integration_depth", "Interoperability & Integration"),
            ("support_service", "Customer Support & Service"),
            ("retention_stickiness", "Retention & Stickiness"),
            ("user_adoption", "User Adoption & Ease of Use"),
            ("implementation_ttv", "Implementation & Time to Value"),
            ("reliability_enterprise", "Reliability & Enterprise Readiness"),
            ("pricing_flexibility", "Pricing & Commercial Flexibility"),
            ("reporting_analytics", "Reporting & Analytics"),
        ]

        for dim_id, dim_name in dimension_fields:
            score_field = f"dim_{dim_id}_score"
            evidence_field = f"dim_{dim_id}_evidence"

            score = getattr(competitor, score_field, None)
            evidence = getattr(competitor, evidence_field, None)

            dimensions[dim_id] = {
                "name": dim_name,
                "score": score,
                "evidence": evidence
            }

            if score:
                total_score += score
                scored_count += 1

        overall_score = (total_score / scored_count) if scored_count > 0 else None

        return {
            "overall_score": overall_score,
            "dimensions": dimensions
        }


if __name__ == "__main__":
    # Test report generation
    test_competitor = {
        "name": "Phreesia",
        "threat_level": "High",
        "year_founded": "2005",
        "headquarters": "Raleigh, NC",
        "employee_count": "1500+",
        "customer_count": "3000+",
        "funding_total": "$300M+",
        "pricing_model": "Per Visit",
        "base_price": "$3.00",
        "product_categories": "Intake; Payments; Scheduling",
        "key_features": "Digital intake, Eligibility verification, Patient payments",
        "target_segments": "Health Systems; Large Practices",
        "g2_rating": "4.5",
        "latest_round": "Public (NYSE: PHR)",
    }
    
    manager = ReportManager("./test_reports")
    path = manager.generate_battlecard(test_competitor)
    print(f"Generated: {path}")
