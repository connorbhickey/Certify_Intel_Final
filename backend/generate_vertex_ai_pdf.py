"""
Generate Vertex AI Implementation Plan PDF
"""
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from datetime import datetime
import os

def generate_vertex_ai_pdf():
    """Generate the Vertex AI Implementation Plan PDF."""

    # Output path
    output_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "VERTEX AI IMPLEMENTATION PLAN.pdf")

    # Create document
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )

    # Styles
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#1a365d')
    )

    heading1_style = ParagraphStyle(
        'CustomH1',
        parent=styles['Heading1'],
        fontSize=16,
        spaceBefore=20,
        spaceAfter=10,
        textColor=colors.HexColor('#2c5282')
    )

    heading2_style = ParagraphStyle(
        'CustomH2',
        parent=styles['Heading2'],
        fontSize=13,
        spaceBefore=15,
        spaceAfter=8,
        textColor=colors.HexColor('#2b6cb0')
    )

    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=6
    )

    # Build content
    story = []

    # Title Page
    story.append(Spacer(1, 1.5*inch))
    story.append(Paragraph("VERTEX AI IMPLEMENTATION PLAN", title_style))
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph("Certify Intel - Competitive Intelligence Platform", styles['Heading2']))
    story.append(Spacer(1, 0.5*inch))

    # Summary table
    summary_data = [
        ["Version", "v5.3.0-VERTEX"],
        ["Status", "PROPOSED (Pending Approval)"],
        ["Date", "January 26, 2026"],
        ["Estimated Effort", "6-8 weeks across 5 phases"],
        ["Total Tasks", "30 tasks"],
        ["New Code", "~6,200 lines across 12 files"],
        ["Estimated Cost", "~$78/month"],
    ]

    summary_table = Table(summary_data, colWidths=[2*inch, 4*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e2e8f0')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1a202c')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e0')),
    ]))
    story.append(summary_table)

    story.append(PageBreak())

    # Executive Summary
    story.append(Paragraph("Executive Summary", heading1_style))
    story.append(Paragraph(
        "This plan outlines the integration of Google Cloud Vertex AI into Certify Intel to enhance "
        "competitive intelligence capabilities with enterprise-grade AI features. The migration from "
        "the consumer Google AI SDK (google-generativeai) to Vertex AI will unlock:",
        normal_style
    ))

    benefits = [
        "<b>Enterprise Security:</b> VPC Service Controls, CMEK encryption, HIPAA compliance",
        "<b>RAG Engine:</b> Grounded responses from competitor knowledge bases",
        "<b>Agent Builder:</b> Autonomous competitive intelligence agents",
        "<b>Vector Search:</b> Semantic search across competitor data",
        "<b>Model Fine-Tuning:</b> Custom models trained on healthcare competitive intelligence",
        "<b>Multi-Agent Systems:</b> Coordinated agents for research, analysis, and reporting",
    ]

    for benefit in benefits:
        story.append(Paragraph(f"  - {benefit}", normal_style))

    story.append(Spacer(1, 0.3*inch))

    # Current vs Proposed
    story.append(Paragraph("Current State vs. Proposed State", heading1_style))

    comparison_data = [
        ["Feature", "Current (Google AI SDK)", "Proposed (Vertex AI)"],
        ["RAG Engine", "Manual implementation", "Managed per-competitor corpora"],
        ["Vector Search", "Keyword-based only", "Semantic search with embeddings"],
        ["Agent Builder", "Manual orchestration", "Autonomous agents with MCP"],
        ["Fine-Tuning", "Not available", "Custom CI model training"],
        ["HIPAA Compliance", "Not available", "Enterprise BAA available"],
        ["Security", "API key authentication", "VPC-SC, CMEK, IAM, audit logs"],
        ["Grounding", "Limited", "Full Google Search + corpus grounding"],
    ]

    comparison_table = Table(comparison_data, colWidths=[1.8*inch, 2.2*inch, 2.5*inch])
    comparison_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5282')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f7fafc')]),
    ]))
    story.append(comparison_table)

    story.append(PageBreak())

    # Implementation Phases
    story.append(Paragraph("Implementation Phases", heading1_style))

    # Phase 1
    story.append(Paragraph("Phase 1: Core Vertex AI Migration (Week 1-2)", heading2_style))
    phase1_data = [
        ["ID", "Task", "Priority"],
        ["VERTEX-1.1", "Set up GCP project with Vertex AI", "HIGH"],
        ["VERTEX-1.2", "Create vertex_ai_provider.py (~800 lines)", "HIGH"],
        ["VERTEX-1.3", "Migrate existing AI calls", "HIGH"],
        ["VERTEX-1.4", "Add service account authentication", "HIGH"],
        ["VERTEX-1.5", "Update .env configuration", "HIGH"],
        ["VERTEX-1.6", "Create provider abstraction", "MEDIUM"],
    ]
    phase1_table = Table(phase1_data, colWidths=[1.2*inch, 4*inch, 1*inch])
    phase1_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#38a169')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e0')),
    ]))
    story.append(phase1_table)
    story.append(Spacer(1, 0.2*inch))

    # Phase 2
    story.append(Paragraph("Phase 2: RAG Engine Integration (Week 2-3)", heading2_style))
    phase2_data = [
        ["ID", "Task", "Priority"],
        ["VERTEX-2.1", "Create RAG corpus management", "HIGH"],
        ["VERTEX-2.2", "Build document ingestion pipeline", "HIGH"],
        ["VERTEX-2.3", "Implement grounded generation", "HIGH"],
        ["VERTEX-2.4", "Add RAG API endpoints", "HIGH"],
        ["VERTEX-2.5", "Integrate with battlecard generator", "MEDIUM"],
        ["VERTEX-2.6", "Add citation extraction", "MEDIUM"],
    ]
    phase2_table = Table(phase2_data, colWidths=[1.2*inch, 4*inch, 1*inch])
    phase2_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3182ce')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e0')),
    ]))
    story.append(phase2_table)
    story.append(Spacer(1, 0.2*inch))

    # Phase 3
    story.append(Paragraph("Phase 3: Vector Search Implementation (Week 3-4)", heading2_style))
    phase3_data = [
        ["ID", "Task", "Priority"],
        ["VERTEX-3.1", "Create Vector Search index", "HIGH"],
        ["VERTEX-3.2", "Build embedding pipeline", "HIGH"],
        ["VERTEX-3.3", "Implement semantic search API", "HIGH"],
        ["VERTEX-3.4", "Add similarity search", "MEDIUM"],
        ["VERTEX-3.5", "Create search UI component", "MEDIUM"],
        ["VERTEX-3.6", "Index historical data", "LOW"],
    ]
    phase3_table = Table(phase3_data, colWidths=[1.2*inch, 4*inch, 1*inch])
    phase3_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#805ad5')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e0')),
    ]))
    story.append(phase3_table)

    story.append(PageBreak())

    # Phase 4
    story.append(Paragraph("Phase 4: Agent Builder Integration (Week 4-6)", heading2_style))
    phase4_data = [
        ["ID", "Task", "Priority"],
        ["VERTEX-4.1", "Create CI Agent definition", "HIGH"],
        ["VERTEX-4.2", "Build MCP tool integrations", "HIGH"],
        ["VERTEX-4.3", "Implement agent memory", "HIGH"],
        ["VERTEX-4.4", "Add scheduled agent tasks", "MEDIUM"],
        ["VERTEX-4.5", "Create agent chat UI", "MEDIUM"],
        ["VERTEX-4.6", "Build alert system", "MEDIUM"],
    ]
    phase4_table = Table(phase4_data, colWidths=[1.2*inch, 4*inch, 1*inch])
    phase4_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#dd6b20')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e0')),
    ]))
    story.append(phase4_table)
    story.append(Spacer(1, 0.2*inch))

    # Phase 5
    story.append(Paragraph("Phase 5: Fine-Tuning & Security (Week 6-8)", heading2_style))
    phase5_data = [
        ["ID", "Task", "Priority"],
        ["VERTEX-5.1", "Prepare fine-tuning dataset", "MEDIUM"],
        ["VERTEX-5.2", "Train custom CI model", "MEDIUM"],
        ["VERTEX-5.3", "Configure VPC-SC", "HIGH"],
        ["VERTEX-5.4", "Set up CMEK", "MEDIUM"],
        ["VERTEX-5.5", "Enable audit logging", "HIGH"],
        ["VERTEX-5.6", "Obtain HIPAA BAA", "HIGH"],
    ]
    phase5_table = Table(phase5_data, colWidths=[1.2*inch, 4*inch, 1*inch])
    phase5_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e53e3e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e0')),
    ]))
    story.append(phase5_table)

    story.append(Spacer(1, 0.3*inch))

    # New Files
    story.append(Paragraph("New Files to Create (12 files, ~6,200 lines)", heading1_style))
    files_data = [
        ["File", "Lines", "Description"],
        ["vertex_ai_provider.py", "~800", "Core Vertex AI provider"],
        ["vertex_config.py", "~200", "Configuration management"],
        ["vertex_rag_engine.py", "~600", "RAG corpus management"],
        ["vertex_vector_search.py", "~500", "Vector Search integration"],
        ["vertex_agent_builder.py", "~1,000", "Agent Builder integration"],
        ["vertex_mcp_tools.py", "~600", "MCP tool definitions"],
        ["vertex_fine_tuning.py", "~400", "Model fine-tuning"],
        ["vertex_security.py", "~300", "Security configuration"],
        ["routers/vertex_rag.py", "~400", "RAG API endpoints"],
        ["routers/vertex_search.py", "~300", "Search API endpoints"],
        ["routers/vertex_agent.py", "~500", "Agent API endpoints"],
        ["frontend/vertex_agent.js", "~600", "Agent chat UI"],
    ]
    files_table = Table(files_data, colWidths=[2.5*inch, 0.8*inch, 3*inch])
    files_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5282')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f7fafc')]),
    ]))
    story.append(files_table)

    story.append(PageBreak())

    # New API Endpoints
    story.append(Paragraph("New API Endpoints (25+)", heading1_style))

    story.append(Paragraph("Vertex AI Provider", heading2_style))
    story.append(Paragraph("GET /api/vertex/status - Provider status", normal_style))
    story.append(Paragraph("GET /api/vertex/models - Available models", normal_style))
    story.append(Paragraph("POST /api/vertex/generate - Text generation", normal_style))
    story.append(Paragraph("POST /api/vertex/embed - Generate embeddings", normal_style))

    story.append(Paragraph("RAG Engine", heading2_style))
    story.append(Paragraph("POST /api/vertex/rag/corpus - Create corpus", normal_style))
    story.append(Paragraph("GET /api/vertex/rag/corpus - List corpora", normal_style))
    story.append(Paragraph("GET /api/vertex/rag/corpus/{id} - Get corpus details", normal_style))
    story.append(Paragraph("DELETE /api/vertex/rag/corpus/{id} - Delete corpus", normal_style))
    story.append(Paragraph("POST /api/vertex/rag/corpus/{id}/ingest - Ingest documents", normal_style))
    story.append(Paragraph("POST /api/vertex/rag/corpus/{id}/query - Query with grounding", normal_style))

    story.append(Paragraph("Vector Search", heading2_style))
    story.append(Paragraph("POST /api/vertex/search - Semantic search", normal_style))
    story.append(Paragraph("POST /api/vertex/search/similar/{id} - Find similar competitors", normal_style))
    story.append(Paragraph("GET /api/vertex/search/index/status - Index status", normal_style))

    story.append(Paragraph("Agent Builder", heading2_style))
    story.append(Paragraph("POST /api/vertex/agent/session - Create session", normal_style))
    story.append(Paragraph("POST /api/vertex/agent/chat - Send message", normal_style))
    story.append(Paragraph("POST /api/vertex/agent/research/{id} - Research competitor", normal_style))
    story.append(Paragraph("GET /api/vertex/agent/alerts - Get alerts", normal_style))
    story.append(Paragraph("POST /api/vertex/agent/monitor/start - Start monitoring", normal_style))

    story.append(Spacer(1, 0.3*inch))

    # Cost Analysis
    story.append(Paragraph("Cost Analysis (~$78/month)", heading1_style))
    cost_data = [
        ["Service", "Usage", "Monthly Cost"],
        ["Gemini 3 Flash (Input)", "50M tokens", "$7.50"],
        ["Gemini 3 Flash (Output)", "25M tokens", "$15.00"],
        ["Gemini 2.5 Pro (complex)", "5M tokens", "$6.25"],
        ["Vector Search Queries", "100K queries", "$10.00"],
        ["Vector Search Storage", "10GB", "$2.50"],
        ["RAG Engine", "10 corpora", "Included"],
        ["Agent Sessions", "1,000 sessions", "$20.00"],
        ["Fine-Tuning (quarterly)", "1 job", "$16.67"],
        ["TOTAL", "", "$77.92"],
    ]
    cost_table = Table(cost_data, colWidths=[2.5*inch, 2*inch, 1.5*inch])
    cost_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#38a169')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#c6f6d5')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e0')),
    ]))
    story.append(cost_table)

    story.append(PageBreak())

    # Success Metrics
    story.append(Paragraph("Success Metrics", heading1_style))
    metrics_data = [
        ["Metric", "Current", "Target"],
        ["AI response accuracy", "~85%", ">95%"],
        ["Hallucination rate", "~15%", "<5%"],
        ["Research time", "30min manual", "5min automated"],
        ["News monitoring", "Manual daily", "Real-time automated"],
        ["Battlecard freshness", "Weekly manual", "Auto-updated"],
        ["Enterprise compliance", "Not compliant", "HIPAA compliant"],
        ["Search relevance", "Keyword only", "Semantic"],
    ]
    metrics_table = Table(metrics_data, colWidths=[2.5*inch, 2*inch, 2*inch])
    metrics_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5282')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f7fafc')]),
    ]))
    story.append(metrics_table)

    story.append(Spacer(1, 0.3*inch))

    # Risks
    story.append(Paragraph("Risks and Mitigations", heading1_style))
    risks_data = [
        ["Risk", "Impact", "Mitigation"],
        ["GCP service outage", "High", "Maintain Google AI SDK fallback"],
        ["Cost overruns", "Medium", "Set budget alerts, optimize queries"],
        ["Fine-tuning quality", "Medium", "Iterative training, human review"],
        ["Agent hallucinations", "Medium", "Grounding required for all responses"],
        ["Migration complexity", "Medium", "Phased rollout, feature flags"],
    ]
    risks_table = Table(risks_data, colWidths=[2*inch, 1*inch, 3.5*inch])
    risks_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e53e3e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e0')),
    ]))
    story.append(risks_table)

    story.append(Spacer(1, 0.5*inch))

    # Conclusion
    story.append(Paragraph("Conclusion", heading1_style))
    story.append(Paragraph(
        "Integrating Vertex AI into Certify Intel will transform the platform from a manual competitive "
        "intelligence tool into an autonomous, enterprise-grade intelligence system. The ~$78/month "
        "investment delivers RAG-grounded responses, autonomous agents, semantic search, custom model "
        "fine-tuning, and HIPAA compliance - capabilities that would cost significantly more to build manually.",
        normal_style
    ))

    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph("<b>Recommended Next Step:</b> Approve plan and begin Phase 1 with GCP project setup.", normal_style))

    story.append(Spacer(1, 0.5*inch))

    # Footer
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
        ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.gray, alignment=TA_CENTER)
    ))
    story.append(Paragraph(
        "Certify Intel v5.0.7 | Vertex AI Integration Plan v5.3.0",
        ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.gray, alignment=TA_CENTER)
    ))

    # Build PDF
    doc.build(story)

    return output_path

if __name__ == "__main__":
    path = generate_vertex_ai_pdf()
    print(f"PDF generated: {path}")
