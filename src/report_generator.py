"""PDF Report Generator for Real Estate OM Analysis"""

from datetime import datetime
from pathlib import Path
from typing import Optional
import sys
import types

# Create a fake PIL module to satisfy reportlab's import without loading native code
# This is needed because PIL may have architecture mismatches on Apple Silicon
def _setup_fake_pil():
    """Set up minimal PIL stub if real PIL fails to load"""
    if 'PIL' in sys.modules:
        try:
            from PIL import Image
            return  # Real PIL works fine
        except (ImportError, OSError):
            pass  # Real PIL broken, replace it

    # Create fake PIL module
    fake_pil = types.ModuleType('PIL')
    fake_pil.__path__ = []

    # Create fake Image module with minimal interface
    fake_image = types.ModuleType('PIL.Image')
    fake_image.Image = None
    fake_image.open = lambda *args, **kwargs: None
    fake_image.LANCZOS = 1
    fake_image.BILINEAR = 2
    fake_image.BICUBIC = 3
    fake_image.NEAREST = 0

    fake_pil.Image = fake_image
    sys.modules['PIL'] = fake_pil
    sys.modules['PIL.Image'] = fake_image

# Try to set up PIL stub before importing reportlab
_setup_fake_pil()

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY

from .models import OMAnalysis, Finding, RiskLevel, PropertyType, ExternalContext


class PDFReportGenerator:
    """Generates professional PDF reports from OM analysis"""

    # Color scheme - clean professional palette
    COLORS = {
        'primary': colors.HexColor('#1e3a5f'),      # Dark navy blue
        'secondary': colors.HexColor('#2d5986'),    # Medium blue
        'accent': colors.HexColor('#4a90d9'),       # Light blue
        'success': colors.HexColor('#2e7d32'),      # Green
        'warning': colors.HexColor('#ed6c02'),      # Orange
        'danger': colors.HexColor('#d32f2f'),       # Red
        'light_bg': colors.HexColor('#f8f9fa'),     # Very light gray
        'alt_row': colors.HexColor('#f1f3f4'),      # Alternating row
        'border': colors.HexColor('#dee2e6'),       # Light border
        'text': colors.HexColor('#212529'),         # Dark text
        'muted': colors.HexColor('#6c757d'),        # Muted text
    }

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Setup custom paragraph styles"""
        # Title style
        self.styles.add(ParagraphStyle(
            name='ReportTitle',
            parent=self.styles['Heading1'],
            fontSize=26,
            textColor=self.COLORS['primary'],
            spaceAfter=8,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
        ))

        # Section header style
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=13,
            textColor=self.COLORS['primary'],
            spaceBefore=18,
            spaceAfter=10,
            fontName='Helvetica-Bold',
            borderPadding=(0, 0, 3, 0),
            borderWidth=0,
            borderColor=self.COLORS['primary'],
        ))

        # Subsection header
        self.styles.add(ParagraphStyle(
            name='SubsectionHeader',
            parent=self.styles['Heading3'],
            fontSize=11,
            textColor=self.COLORS['secondary'],
            spaceBefore=12,
            spaceAfter=6,
            fontName='Helvetica-Bold',
        ))

        # Table cell styles
        self.styles.add(ParagraphStyle(
            name='TableLabel',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=self.COLORS['text'],
            fontName='Helvetica-Bold',
            leading=12,
        ))

        self.styles.add(ParagraphStyle(
            name='TableValue',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=self.COLORS['text'],
            fontName='Helvetica',
            leading=12,
            wordWrap='CJK',  # Enable word wrapping
        ))

        # Body text
        self.styles.add(ParagraphStyle(
            name='CustomBodyText',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=self.COLORS['text'],
            spaceAfter=6,
            leading=13,
        ))

        # Finding styles
        self.styles.add(ParagraphStyle(
            name='ProText',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=self.COLORS['success'],
            leftIndent=12,
            spaceAfter=3,
            fontName='Helvetica-Bold',
        ))

        self.styles.add(ParagraphStyle(
            name='ConText',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=self.COLORS['warning'],
            leftIndent=12,
            spaceAfter=3,
            fontName='Helvetica-Bold',
        ))

        self.styles.add(ParagraphStyle(
            name='RedFlagText',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=self.COLORS['danger'],
            leftIndent=12,
            spaceAfter=3,
            fontName='Helvetica-Bold',
        ))

        # Detail text for findings
        self.styles.add(ParagraphStyle(
            name='DetailText',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=self.COLORS['muted'],
            leftIndent=20,
            spaceAfter=8,
            leading=11,
        ))

        # Metric detail
        self.styles.add(ParagraphStyle(
            name='MetricDetail',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=self.COLORS['muted'],
            leftIndent=20,
            spaceAfter=10,
        ))

    def generate_report(self, analysis: OMAnalysis, output_path: str) -> str:
        """Generate a PDF report from the analysis"""
        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=0.6 * inch,
            leftMargin=0.6 * inch,
            topMargin=0.5 * inch,
            bottomMargin=0.5 * inch,
        )

        story = []

        # Compact header with score
        story.extend(self._build_compact_header(analysis))

        # Combined key metrics section
        story.extend(self._build_key_metrics(analysis))

        # Detailed Analysis (the main content)
        story.extend(self._build_analysis_section(analysis))

        # External Context (news, government data, analyst insights)
        story.extend(self._build_external_context_section(analysis))

        doc.build(story)
        return output_path

    def _build_compact_header(self, analysis: OMAnalysis) -> list:
        """Build a compact header with property name, location, and score"""
        elements = []

        # Property name
        property_name = analysis.property.name or "Real Estate Investment Analysis"
        elements.append(Paragraph(property_name, self.styles['ReportTitle']))

        # Location + date on one line
        location_parts = []
        if analysis.property.city:
            location_parts.append(analysis.property.city)
        if analysis.property.state:
            location_parts.append(analysis.property.state)
        location_str = ", ".join(location_parts) if location_parts else ""
        date_str = datetime.now().strftime('%B %d, %Y')
        subtitle = f"{location_str}  |  {date_str}" if location_str else date_str

        elements.append(Paragraph(
            subtitle,
            ParagraphStyle(
                'SubtitleLine',
                parent=self.styles['Normal'],
                fontSize=10,
                textColor=self.COLORS['muted'],
                alignment=TA_CENTER,
                spaceAfter=12,
            )
        ))

        # Score badge - prominent display
        score = analysis.overall_score or 0
        if score >= 60:
            score_color = self.COLORS['success']
            score_label = "FAVORABLE"
        elif score >= 45:
            score_color = self.COLORS['warning']
            score_label = "MIXED"
        else:
            score_color = self.COLORS['danger']
            score_label = "CONCERNS"

        score_data = [[
            Paragraph(f'<font size="22"><b>{score}</b></font><font size="10">/100</font>',
                     ParagraphStyle('ScoreBig', parent=self.styles['Normal'],
                                   textColor=score_color, alignment=TA_CENTER)),
            Paragraph(f'<b>{score_label}</b>',
                     ParagraphStyle('ScoreLabel', parent=self.styles['Normal'],
                                   textColor=score_color, fontSize=11, alignment=TA_CENTER))
        ]]

        score_table = Table(score_data, colWidths=[1.2 * inch, 1.5 * inch])
        score_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BOX', (0, 0), (-1, -1), 2, score_color),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))

        # Center the score table
        outer_table = Table([[score_table]], colWidths=[7 * inch])
        outer_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        elements.append(outer_table)
        elements.append(Spacer(1, 15))

        return elements

    def _build_key_metrics(self, analysis: OMAnalysis) -> list:
        """Build a compact key metrics section combining property, financials, deal terms"""
        elements = []

        prop = analysis.property
        fin = analysis.financials
        terms = analysis.deal_terms
        fees = analysis.fees

        # ===== ROW 1: Property + Valuation side by side =====
        # Property details (left column)
        prop_rows = []
        if prop.property_type and prop.property_type != PropertyType.UNKNOWN:
            prop_rows.append(['Type', prop.property_type.value.replace('_', ' ').title()])
        if prop.year_built:
            age = datetime.now().year - prop.year_built
            prop_rows.append(['Built', f"{prop.year_built} ({age} yrs)"])
        if prop.num_buildings:
            prop_rows.append(['Buildings', str(prop.num_buildings)])
        if prop.total_units and prop.total_units != prop.num_buildings:
            prop_rows.append(['Units', str(prop.total_units)])
        if prop.num_tenants:
            prop_rows.append(['Tenants', str(prop.num_tenants)])
        if prop.total_sqft:
            prop_rows.append(['Size', f"{prop.total_sqft:,.0f} SF"])
        if prop.walt_years:
            prop_rows.append(['WALT', f"{prop.walt_years:.1f} yrs"])
        if prop.lot_size_acres:
            prop_rows.append(['Land', f"{prop.lot_size_acres:.2f} ac"])

        # Valuation details (right column)
        val_rows = []
        if fin.asking_price:
            val_rows.append(['Price', f"${fin.asking_price:,.0f}"])
        if fin.price_per_sqft:
            val_rows.append(['$/SF', f"${fin.price_per_sqft:,.2f}"])
        if fin.price_per_unit:
            val_rows.append(['$/Unit', f"${fin.price_per_unit:,.0f}"])
        if fin.current_cap_rate:
            val_rows.append(['Cap Rate', f"{fin.current_cap_rate:.2%}"])
        if fin.current_noi:
            val_rows.append(['NOI', f"${fin.current_noi:,.0f}"])
        if fin.current_occupancy:
            val_rows.append(['Occupancy', f"{fin.current_occupancy:.1%}"])

        # Build the two mini tables
        if prop_rows or val_rows:
            elements.append(self._build_two_column_section(
                "PROPERTY", prop_rows,
                "VALUATION", val_rows
            ))
            elements.append(Spacer(1, 10))

        # ===== ROW 2: Returns + Deal Terms side by side =====
        # Returns details (left column)
        ret_rows = []
        if fin.irr_projected:
            ret_rows.append(['Target IRR', f"{fin.irr_projected:.1%}"])
        if fin.equity_multiple:
            ret_rows.append(['Equity Multiple', f"{fin.equity_multiple:.2f}x"])
        if fin.cash_on_cash_return:
            ret_rows.append(['Cash-on-Cash', f"{fin.cash_on_cash_return:.1%}"])
        if terms.preferred_return:
            ret_rows.append(['Pref Return', f"{terms.preferred_return:.1%}"])

        # Deal terms (right column)
        deal_rows = []
        if terms.loan_to_value:
            deal_rows.append(['LTV', f"{terms.loan_to_value:.1%}"])
        if terms.interest_rate:
            deal_rows.append(['Rate', f"{terms.interest_rate:.2%}"])
        if terms.hold_period_years:
            deal_rows.append(['Hold', f"{terms.hold_period_years} yrs"])
        if terms.minimum_investment:
            deal_rows.append(['Min Invest', f"${terms.minimum_investment:,.0f}"])
        if terms.profit_split:
            deal_rows.append(['Split (LP/GP)', terms.profit_split])

        if ret_rows or deal_rows:
            elements.append(self._build_two_column_section(
                "RETURNS", ret_rows,
                "DEAL TERMS", deal_rows
            ))
            elements.append(Spacer(1, 10))

        # ===== ROW 3: Fees (single row, compact) =====
        fee_items = []
        if fees.acquisition_fee:
            fee_items.append(f"Acq: {fees.acquisition_fee:.1%}")
        if fees.asset_management_fee:
            fee_items.append(f"AM: {fees.asset_management_fee:.1%}/yr")
        if fees.property_management_fee:
            fee_items.append(f"PM: {fees.property_management_fee:.1%}")
        if fees.disposition_fee:
            fee_items.append(f"Disp: {fees.disposition_fee:.1%}")

        if fee_items:
            fee_text = "  |  ".join(fee_items)
            elements.append(Paragraph("SPONSOR FEES", self.styles['SubsectionHeader']))
            elements.append(Paragraph(
                fee_text,
                ParagraphStyle('FeeRow', parent=self.styles['Normal'],
                              fontSize=9, textColor=self.COLORS['text'])
            ))
            elements.append(Spacer(1, 10))

        # Divider before detailed analysis
        elements.append(HRFlowable(
            width="100%",
            thickness=1.5,
            color=self.COLORS['primary'],
            spaceAfter=10,
        ))

        return elements

    def _build_two_column_section(self, left_title: str, left_data: list,
                                   right_title: str, right_data: list) -> Table:
        """Build a two-column section with headers and data using a flat 4-column table"""
        # Create styles
        header_style = ParagraphStyle('ColHeader', parent=self.styles['Normal'],
                                      fontSize=10, textColor=self.COLORS['primary'],
                                      fontName='Helvetica-Bold')
        label_style = ParagraphStyle('ColLabel', parent=self.styles['Normal'],
                                     fontSize=8, textColor=self.COLORS['muted'])
        value_style = ParagraphStyle('ColValue', parent=self.styles['Normal'],
                                     fontSize=9, textColor=self.COLORS['text'],
                                     fontName='Helvetica-Bold')

        # Build rows: [left_label, left_value, right_label, right_value]
        rows = []

        # Header row
        rows.append([
            Paragraph(f'<b>{left_title}</b>', header_style), '',
            Paragraph(f'<b>{right_title}</b>', header_style), ''
        ])

        # Determine max rows needed
        max_rows = max(len(left_data), len(right_data))

        # Data rows
        for i in range(max_rows):
            row = ['', '', '', '']
            if i < len(left_data):
                row[0] = Paragraph(f'{left_data[i][0]}:', label_style)
                row[1] = Paragraph(left_data[i][1], value_style)
            if i < len(right_data):
                row[2] = Paragraph(f'{right_data[i][0]}:', label_style)
                row[3] = Paragraph(right_data[i][1], value_style)
            rows.append(row)

        # Create table with 4 columns
        table = Table(rows, colWidths=[1.0 * inch, 1.4 * inch, 1.0 * inch, 1.4 * inch])
        table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            # Header row spans
            ('SPAN', (0, 0), (1, 0)),  # Left header spans 2 columns
            ('SPAN', (2, 0), (3, 0)),  # Right header spans 2 columns
            # Visual styling
            ('BOX', (0, 0), (-1, -1), 0.5, self.COLORS['border']),
            ('LINEBEFORE', (2, 0), (2, -1), 0.5, self.COLORS['border']),  # Vertical divider
            ('BACKGROUND', (0, 0), (-1, -1), self.COLORS['light_bg']),
        ]))

        return table

    def _build_header(self, analysis: OMAnalysis) -> list:
        """Build the report header"""
        elements = []

        # Property name
        property_name = analysis.property.name or "Real Estate Investment Analysis"
        elements.append(Paragraph(property_name, self.styles['ReportTitle']))

        # Location subtitle
        location_parts = []
        if analysis.property.city:
            location_parts.append(analysis.property.city)
        if analysis.property.state:
            location_parts.append(analysis.property.state)
        if location_parts:
            elements.append(Paragraph(
                ", ".join(location_parts),
                ParagraphStyle(
                    'LocationLine',
                    parent=self.styles['Normal'],
                    fontSize=11,
                    textColor=self.COLORS['muted'],
                    alignment=TA_CENTER,
                    spaceAfter=4,
                )
            ))

        # Report date
        elements.append(Paragraph(
            f"Analysis Date: {datetime.now().strftime('%B %d, %Y')}",
            ParagraphStyle(
                'DateLine',
                parent=self.styles['Normal'],
                fontSize=9,
                textColor=self.COLORS['muted'],
                alignment=TA_CENTER,
                spaceAfter=15,
            )
        ))

        # Divider line
        elements.append(HRFlowable(
            width="100%",
            thickness=1.5,
            color=self.COLORS['primary'],
            spaceAfter=15,
        ))

        return elements

    def _build_executive_summary(self, analysis: OMAnalysis) -> list:
        """Build the executive summary section"""
        elements = []
        elements.append(Paragraph("EXECUTIVE SUMMARY", self.styles['SectionHeader']))

        score = analysis.overall_score or 0
        recommendation = analysis.recommendation or "Analysis pending"

        # Score color
        if score >= 60:
            score_color = self.COLORS['success']
        elif score >= 45:
            score_color = self.COLORS['warning']
        else:
            score_color = self.COLORS['danger']

        # Summary data with Paragraphs for wrapping
        summary_data = [
            [Paragraph('<b>Deal Score</b>', self.styles['TableLabel']),
             Paragraph(f'<b><font size="14">{score}/100</font></b>',
                      ParagraphStyle('ScoreValue', parent=self.styles['TableValue'],
                                    textColor=score_color, fontSize=14))],
            [Paragraph('<b>Recommendation</b>', self.styles['TableLabel']),
             Paragraph(recommendation, self.styles['TableValue'])],
            [Paragraph('<b>Strengths</b>', self.styles['TableLabel']),
             Paragraph(str(len(analysis.pros)), self.styles['TableValue'])],
            [Paragraph('<b>Concerns</b>', self.styles['TableLabel']),
             Paragraph(str(len(analysis.cons)), self.styles['TableValue'])],
            [Paragraph('<b>Red Flags</b>', self.styles['TableLabel']),
             Paragraph(str(len(analysis.red_flags)), self.styles['TableValue'])],
        ]

        summary_table = Table(summary_data, colWidths=[2.2 * inch, 4.5 * inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), self.COLORS['light_bg']),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('LINEBELOW', (0, 0), (-1, -2), 0.5, self.COLORS['border']),
            ('LINEAFTER', (0, 0), (0, -1), 0.5, self.COLORS['border']),
            ('BOX', (0, 0), (-1, -1), 1, self.COLORS['border']),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 12))

        # Key highlights
        if analysis.pros:
            elements.append(Paragraph("Key Strengths:", self.styles['SubsectionHeader']))
            for pro in analysis.pros[:3]:
                elements.append(Paragraph(f"• {pro.description}", self.styles['ProText']))

        if analysis.red_flags:
            elements.append(Spacer(1, 8))
            elements.append(Paragraph("Critical Concerns:", self.styles['SubsectionHeader']))
            for flag in analysis.red_flags[:3]:
                elements.append(Paragraph(f"• {flag.description}", self.styles['RedFlagText']))

        elements.append(Spacer(1, 12))
        return elements

    def _build_property_section(self, analysis: OMAnalysis) -> list:
        """Build the property details section"""
        elements = []
        elements.append(Paragraph("PROPERTY OVERVIEW", self.styles['SectionHeader']))

        prop = analysis.property
        data = []

        if prop.property_type and prop.property_type != PropertyType.UNKNOWN:
            data.append(['Property Type', prop.property_type.value.replace('_', ' ').title()])
        if prop.address:
            data.append(['Address', prop.address])
        if prop.city or prop.state:
            location = f"{prop.city or ''}, {prop.state or ''} {prop.zip_code or ''}".strip(', ')
            data.append(['Location', location])
        if prop.year_built:
            age = datetime.now().year - prop.year_built
            data.append(['Year Built', f"{prop.year_built} ({age} years old)"])
        if prop.num_buildings:
            data.append(['Buildings', str(prop.num_buildings)])
        if prop.total_units and prop.total_units != prop.num_buildings:
            data.append(['Total Units', str(prop.total_units)])
        if prop.num_tenants:
            data.append(['Tenants', str(prop.num_tenants)])
        if prop.total_sqft:
            data.append(['Square Footage', f"{prop.total_sqft:,.0f} SF"])
        if prop.walt_years:
            data.append(['Avg. Lease Term (WALT)', f"{prop.walt_years:.1f} years"])
        if prop.lot_size_acres:
            data.append(['Land Area', f"{prop.lot_size_acres:.2f} acres"])
        if prop.amenities:
            data.append(['Features', ', '.join(prop.amenities[:6])])

        if data:
            table = self._create_data_table(data)
            elements.append(table)
        else:
            elements.append(Paragraph(
                "Property details not available.",
                self.styles['CustomBodyText']
            ))

        elements.append(Spacer(1, 12))
        return elements

    def _build_financials_section(self, analysis: OMAnalysis) -> list:
        """Build the financial metrics section"""
        elements = []
        elements.append(Paragraph("FINANCIAL SUMMARY", self.styles['SectionHeader']))

        fin = analysis.financials

        # Valuation data
        val_data = []
        if fin.asking_price:
            val_data.append(['Purchase Price', f"${fin.asking_price:,.0f}"])
        if fin.price_per_unit:
            val_data.append(['Price Per Unit', f"${fin.price_per_unit:,.0f}"])
        if fin.price_per_sqft:
            val_data.append(['Price Per SF', f"${fin.price_per_sqft:,.2f}"])
        if fin.current_cap_rate:
            val_data.append(['Going-In Cap Rate', f"{fin.current_cap_rate:.2%}"])
        if fin.proforma_cap_rate:
            val_data.append(['Exit Cap Rate', f"{fin.proforma_cap_rate:.2%}"])
        if fin.current_noi:
            val_data.append(['Net Operating Income', f"${fin.current_noi:,.0f}"])
        if fin.current_occupancy:
            val_data.append(['Occupancy', f"{fin.current_occupancy:.1%}"])

        # Return metrics
        return_data = []
        if fin.irr_projected:
            return_data.append(['Projected IRR', f"{fin.irr_projected:.1%}"])
        if fin.equity_multiple:
            return_data.append(['Equity Multiple', f"{fin.equity_multiple:.2f}x"])
        if fin.cash_on_cash_return:
            return_data.append(['Cash-on-Cash', f"{fin.cash_on_cash_return:.1%}"])

        if val_data:
            elements.append(Paragraph("Valuation", self.styles['SubsectionHeader']))
            table = self._create_data_table(val_data)
            elements.append(table)

        if return_data:
            elements.append(Spacer(1, 8))
            elements.append(Paragraph("Projected Returns", self.styles['SubsectionHeader']))
            table = self._create_data_table(return_data)
            elements.append(table)

        if not val_data and not return_data:
            elements.append(Paragraph(
                "Financial metrics not available.",
                self.styles['CustomBodyText']
            ))

        elements.append(Spacer(1, 12))
        return elements

    def _build_deal_terms_section(self, analysis: OMAnalysis) -> list:
        """Build the deal terms section"""
        elements = []
        elements.append(Paragraph("DEAL STRUCTURE", self.styles['SectionHeader']))

        terms = analysis.deal_terms
        data = []

        if terms.loan_amount:
            data.append(['Senior Debt', f"${terms.loan_amount:,.0f}"])
        if terms.loan_to_value:
            data.append(['Loan-to-Value', f"{terms.loan_to_value:.1%}"])
        if terms.interest_rate:
            data.append(['Interest Rate', f"{terms.interest_rate:.2%}"])
        if terms.loan_type:
            data.append(['Loan Type', terms.loan_type])
        if terms.minimum_investment:
            data.append(['Minimum Investment', f"${terms.minimum_investment:,.0f}"])
        if terms.preferred_return:
            data.append(['Preferred Return', f"{terms.preferred_return:.1%}"])
        if terms.profit_split:
            data.append(['Profit Split (LP/GP)', terms.profit_split])
        if terms.hold_period_years:
            data.append(['Hold Period', f"{terms.hold_period_years} years"])

        if data:
            table = self._create_data_table(data)
            elements.append(table)
        else:
            elements.append(Paragraph(
                "Deal terms not available.",
                self.styles['CustomBodyText']
            ))

        elements.append(Spacer(1, 12))
        return elements

    def _build_fees_section(self, analysis: OMAnalysis) -> list:
        """Build the sponsor fees section"""
        elements = []
        elements.append(Paragraph("SPONSOR FEES", self.styles['SectionHeader']))

        fees = analysis.fees
        data = []

        if fees.acquisition_fee:
            data.append(['Acquisition Fee', f"{fees.acquisition_fee:.2%}"])
        if fees.asset_management_fee:
            data.append(['Asset Management', f"{fees.asset_management_fee:.2%} /year"])
        if fees.property_management_fee:
            data.append(['Property Management', f"{fees.property_management_fee:.2%}"])
        if fees.construction_management_fee:
            data.append(['Construction Mgmt', f"{fees.construction_management_fee:.2%}"])
        if fees.disposition_fee:
            data.append(['Disposition Fee', f"{fees.disposition_fee:.2%}"])
        if fees.estimated_total_fees_over_hold:
            data.append(['Total Est. Fees', f"{fees.estimated_total_fees_over_hold:.1%}"])

        if data:
            table = self._create_data_table(data)
            elements.append(table)
            elements.append(Spacer(1, 6))
            elements.append(Paragraph(
                "<i>Benchmarks: Acquisition 1%, Asset Mgmt 1.5%/yr, Property Mgmt 5%, Disposition 1%</i>",
                ParagraphStyle('Note', parent=self.styles['Normal'],
                              fontSize=8, textColor=self.COLORS['muted'])
            ))
        else:
            elements.append(Paragraph(
                "Fee structure not disclosed. Request detailed fee schedule.",
                self.styles['CustomBodyText']
            ))

        elements.append(Spacer(1, 12))
        return elements

    def _has_market_data(self, analysis: OMAnalysis) -> bool:
        """Check if meaningful market data exists"""
        market = analysis.market_data
        return any([
            market.market_vacancy_rate,
            market.market_rent_psf,
            market.market_cap_rate,
            market.rent_growth_1yr,
        ])

    def _build_market_section(self, analysis: OMAnalysis) -> list:
        """Build the market data section"""
        elements = []
        elements.append(Paragraph("MARKET DATA", self.styles['SectionHeader']))

        market = analysis.market_data
        data = []

        if market.market_vacancy_rate:
            data.append(['Market Vacancy', f"{market.market_vacancy_rate:.1%}"])
        if market.market_rent_psf:
            data.append(['Market Rent (PSF)', f"${market.market_rent_psf:.2f}"])
        if market.market_cap_rate:
            data.append(['Market Cap Rate', f"{market.market_cap_rate:.2%}"])
        if market.rent_growth_1yr:
            data.append(['Rent Growth (1yr)', f"{market.rent_growth_1yr:.1%}"])
        if market.job_growth:
            data.append(['Job Growth', f"{market.job_growth:.1%}"])
        if market.median_household_income:
            data.append(['Median Income', f"${market.median_household_income:,.0f}"])

        if data:
            table = self._create_data_table(data)
            elements.append(table)

        elements.append(Spacer(1, 12))
        return elements

    def _build_analysis_section(self, analysis: OMAnalysis) -> list:
        """Build the detailed analysis section"""
        elements = []

        # Strengths
        if analysis.pros:
            elements.append(Paragraph("Strengths", self.styles['SubsectionHeader']))
            for i, pro in enumerate(analysis.pros, 1):
                elements.append(Paragraph(
                    f"{i}. {pro.description}",
                    self.styles['ProText']
                ))
                if pro.details:
                    elements.append(Paragraph(pro.details, self.styles['DetailText']))
                if pro.actual_value and pro.benchmark_value:
                    elements.append(Paragraph(
                        f"Value: {pro.actual_value} | Benchmark: {pro.benchmark_value}",
                        self.styles['MetricDetail']
                    ))
            elements.append(Spacer(1, 10))

        # Concerns
        if analysis.cons:
            elements.append(Paragraph("Concerns", self.styles['SubsectionHeader']))
            for i, con in enumerate(analysis.cons, 1):
                elements.append(Paragraph(
                    f"{i}. {con.description}",
                    self.styles['ConText']
                ))
                if con.details:
                    elements.append(Paragraph(con.details, self.styles['DetailText']))
                if con.actual_value and con.benchmark_value:
                    elements.append(Paragraph(
                        f"Value: {con.actual_value} | Benchmark: {con.benchmark_value}",
                        self.styles['MetricDetail']
                    ))
            elements.append(Spacer(1, 10))

        # Red Flags
        if analysis.red_flags:
            elements.append(Paragraph("Red Flags", self.styles['SubsectionHeader']))
            for i, flag in enumerate(analysis.red_flags, 1):
                risk = f" - {flag.risk_level.value}" if flag.risk_level else ""
                elements.append(Paragraph(
                    f"{i}. {flag.description}{risk}",
                    self.styles['RedFlagText']
                ))
                if flag.details:
                    elements.append(Paragraph(flag.details, self.styles['DetailText']))
                if flag.actual_value and flag.benchmark_value:
                    elements.append(Paragraph(
                        f"Value: {flag.actual_value} | Benchmark: {flag.benchmark_value}",
                        self.styles['MetricDetail']
                    ))
            elements.append(Spacer(1, 10))

        # Final recommendation
        elements.append(Spacer(1, 10))

        recommendation = analysis.recommendation or "Analysis pending"
        score = analysis.overall_score or 0

        if score >= 60:
            rec_color = self.COLORS['success']
        elif score >= 45:
            rec_color = self.COLORS['warning']
        else:
            rec_color = self.COLORS['danger']

        elements.append(Paragraph(
            f"<b>{recommendation}</b>",
            ParagraphStyle(
                'FinalRec',
                parent=self.styles['Normal'],
                fontSize=11,
                textColor=rec_color,
                alignment=TA_CENTER,
                spaceBefore=8,
                spaceAfter=15,
            )
        ))

        return elements

    def _build_external_context_section(self, analysis: OMAnalysis) -> list:
        """Build the external context section with news, government data, and analyst insights"""
        elements = []
        ctx = analysis.external_context

        # Only add section if there's meaningful data
        has_data = (ctx.economic_indicators or ctx.market_news or
                    ctx.analyst_insights or ctx.supply_pipeline)
        if not has_data:
            return elements

        elements.append(PageBreak())
        elements.append(Paragraph("MARKET CONTEXT & EXTERNAL DATA", self.styles['SectionHeader']))
        elements.append(Spacer(1, 6))

        # Economic Indicators
        if ctx.economic_indicators:
            elements.append(Paragraph("Economic Indicators", self.styles['SubsectionHeader']))
            indicator_data = []
            for ind in ctx.economic_indicators[:6]:  # Limit to 6
                trend_symbol = {'up': '\u2191', 'down': '\u2193', 'stable': '\u2192'}.get(ind.trend, '')
                indicator_data.append([
                    f"{ind.name}",
                    f"{ind.value}{ind.unit} {trend_symbol}",
                ])
            if indicator_data:
                table = self._create_data_table(indicator_data)
                elements.append(table)
                # Add source note
                sources = set(ind.source for ind in ctx.economic_indicators)
                elements.append(Paragraph(
                    f"<i>Sources: {', '.join(list(sources)[:3])}</i>",
                    ParagraphStyle('SourceNote', parent=self.styles['Normal'],
                                  fontSize=7, textColor=self.COLORS['muted'])
                ))
            elements.append(Spacer(1, 12))

        # Analyst Insights
        if ctx.analyst_insights:
            elements.append(Paragraph("Analyst Insights", self.styles['SubsectionHeader']))
            for insight in ctx.analyst_insights[:4]:  # Limit to 4
                elements.append(Paragraph(
                    f"<b>{insight.source}</b> - {insight.title}",
                    ParagraphStyle('InsightHeader', parent=self.styles['Normal'],
                                  fontSize=9, textColor=self.COLORS['secondary'])
                ))
                elements.append(Paragraph(
                    insight.key_finding,
                    self.styles['CustomBodyText']
                ))
                if insight.forecast:
                    elements.append(Paragraph(
                        f"<i>Forecast: {insight.forecast}</i>",
                        ParagraphStyle('Forecast', parent=self.styles['Normal'],
                                      fontSize=8, textColor=self.COLORS['muted'],
                                      leftIndent=10)
                    ))
                elements.append(Spacer(1, 6))
            elements.append(Spacer(1, 6))

        # Market News
        if ctx.market_news:
            elements.append(Paragraph("Market News & Trends", self.styles['SubsectionHeader']))
            for news in ctx.market_news[:4]:  # Limit to 4
                # Sentiment indicator
                sentiment_color = {
                    'positive': self.COLORS['success'],
                    'negative': self.COLORS['danger'],
                    'neutral': self.COLORS['muted']
                }.get(news.sentiment, self.COLORS['text'])

                elements.append(Paragraph(
                    f"<b>{news.headline}</b>",
                    ParagraphStyle('NewsHeadline', parent=self.styles['Normal'],
                                  fontSize=9, textColor=sentiment_color)
                ))
                elements.append(Paragraph(
                    f"{news.summary}",
                    ParagraphStyle('NewsSummary', parent=self.styles['Normal'],
                                  fontSize=8, textColor=self.COLORS['text'],
                                  leftIndent=10)
                ))
                elements.append(Paragraph(
                    f"<i>— {news.source}, {news.date}</i>",
                    ParagraphStyle('NewsSource', parent=self.styles['Normal'],
                                  fontSize=7, textColor=self.COLORS['muted'],
                                  leftIndent=10)
                ))
                elements.append(Spacer(1, 6))
            elements.append(Spacer(1, 6))

        # Supply Pipeline
        if ctx.supply_pipeline:
            elements.append(Paragraph("Supply Pipeline", self.styles['SubsectionHeader']))
            pipeline_data = []
            for key, value in ctx.supply_pipeline.items():
                if key != 'source' and value:
                    label = key.replace('_', ' ').title()
                    pipeline_data.append([label, str(value)])
            if pipeline_data:
                table = self._create_data_table(pipeline_data)
                elements.append(table)
            elements.append(Spacer(1, 12))

        # Regulatory Risks
        if ctx.regulatory_risks:
            elements.append(Paragraph("Regulatory Considerations", self.styles['SubsectionHeader']))
            for risk in ctx.regulatory_risks[:4]:
                elements.append(Paragraph(
                    f"\u2022 {risk}",
                    ParagraphStyle('RiskItem', parent=self.styles['Normal'],
                                  fontSize=8, textColor=self.COLORS['warning'],
                                  leftIndent=10)
                ))
            elements.append(Spacer(1, 8))

        # Environmental Notes
        if ctx.environmental_notes:
            elements.append(Paragraph("Environmental Considerations", self.styles['SubsectionHeader']))
            for note in ctx.environmental_notes[:3]:
                elements.append(Paragraph(
                    f"\u2022 {note}",
                    ParagraphStyle('EnvNote', parent=self.styles['Normal'],
                                  fontSize=8, textColor=self.COLORS['muted'],
                                  leftIndent=10)
                ))
            elements.append(Spacer(1, 8))

        # Data Sources footer
        if ctx.data_sources_used:
            elements.append(HRFlowable(
                width="100%",
                thickness=0.5,
                color=self.COLORS['border'],
                spaceBefore=10,
                spaceAfter=6,
            ))
            elements.append(Paragraph(
                f"<i>Data sources: {', '.join(ctx.data_sources_used)}</i>",
                ParagraphStyle('DataSources', parent=self.styles['Normal'],
                              fontSize=7, textColor=self.COLORS['muted'])
            ))
            if ctx.last_updated:
                elements.append(Paragraph(
                    f"<i>Last updated: {ctx.last_updated}</i>",
                    ParagraphStyle('LastUpdated', parent=self.styles['Normal'],
                                  fontSize=7, textColor=self.COLORS['muted'])
                ))

        return elements

    def _create_data_table(self, data: list) -> Table:
        """Create a clean, styled data table with word wrapping"""
        # Convert to Paragraphs for word wrapping
        formatted_data = []
        for row in data:
            formatted_data.append([
                Paragraph(f"<b>{row[0]}</b>", self.styles['TableLabel']),
                Paragraph(str(row[1]), self.styles['TableValue'])
            ])

        table = Table(formatted_data, colWidths=[2.0 * inch, 4.7 * inch])

        # Build style with alternating rows
        style_commands = [
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('LINEBELOW', (0, 0), (-1, -2), 0.5, self.COLORS['border']),
            ('BOX', (0, 0), (-1, -1), 0.5, self.COLORS['border']),
        ]

        # Add alternating row backgrounds
        for i in range(len(formatted_data)):
            if i % 2 == 0:
                style_commands.append(('BACKGROUND', (0, i), (-1, i), self.COLORS['light_bg']))

        table.setStyle(TableStyle(style_commands))
        return table
