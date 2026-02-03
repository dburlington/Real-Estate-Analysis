#!/usr/bin/env python3
"""Diagnostic tool to debug PDF extraction issues"""

import sys
from pathlib import Path

def diagnose_pdf(file_path: str):
    """Diagnose PDF extraction and show what's being captured"""
    from src.om_parser import OMParser, PDFExtractor

    print(f"\n{'='*60}")
    print(f"DIAGNOSING: {file_path}")
    print(f"{'='*60}\n")

    # Step 1: Extract raw text
    print("[1] EXTRACTING TEXT FROM PDF...")
    extractor = PDFExtractor()
    try:
        raw_text = extractor.extract(file_path)
        print(f"    Extraction method: {extractor.extraction_method}")
        print(f"    Total characters: {len(raw_text)}")
        print(f"    Is scanned PDF: {extractor.is_scanned}")
        if extractor.errors:
            print(f"    Errors: {extractor.errors}")
    except Exception as e:
        print(f"    EXTRACTION FAILED: {e}")
        return

    # Step 2: Show sample of extracted text
    print(f"\n[2] FIRST 2000 CHARACTERS OF EXTRACTED TEXT:")
    print("-" * 60)
    print(raw_text[:2000])
    print("-" * 60)

    # Step 3: Parse with OMParser
    print(f"\n[3] PARSING EXTRACTED TEXT...")
    parser = OMParser()
    analysis = parser.parse_text(raw_text)

    # Step 4: Show what was extracted
    print(f"\n[4] EXTRACTED PROPERTY DETAILS:")
    prop = analysis.property
    print(f"    Name: {prop.name or '(not found)'}")
    print(f"    Address: {prop.address or '(not found)'}")
    print(f"    City: {prop.city or '(not found)'}")
    print(f"    State: {prop.state or '(not found)'}")
    print(f"    Zip: {prop.zip_code or '(not found)'}")
    print(f"    Property Type: {prop.property_type}")
    print(f"    Units: {prop.total_units or '(not found)'}")
    print(f"    Buildings: {prop.num_buildings or '(not found)'}")
    print(f"    Tenants: {prop.num_tenants or '(not found)'}")
    print(f"    Sq Ft: {prop.total_sqft or '(not found)'}")
    print(f"    Year Built: {prop.year_built or '(not found)'}")
    print(f"    WALT: {prop.walt_years:.1f} years" if prop.walt_years else "    WALT: (not found)")

    print(f"\n[5] EXTRACTED FINANCIAL METRICS:")
    fin = analysis.financials
    print(f"    Asking Price: ${fin.asking_price:,.0f}" if fin.asking_price else "    Asking Price: (not found)")
    print(f"    Price/Unit: ${fin.price_per_unit:,.0f}" if fin.price_per_unit else "    Price/Unit: (not found)")
    print(f"    Cap Rate: {fin.current_cap_rate:.2%}" if fin.current_cap_rate else "    Cap Rate: (not found)")
    print(f"    Pro Forma Cap: {fin.proforma_cap_rate:.2%}" if fin.proforma_cap_rate else "    Pro Forma Cap: (not found)")
    print(f"    NOI: ${fin.current_noi:,.0f}" if fin.current_noi else "    NOI: (not found)")
    print(f"    Occupancy: {fin.current_occupancy:.1%}" if fin.current_occupancy else "    Occupancy: (not found)")
    print(f"    Avg Rent: ${fin.average_rent:,.0f}" if fin.average_rent else "    Avg Rent: (not found)")
    print(f"    IRR: {fin.irr_projected:.1%}" if fin.irr_projected else "    IRR: (not found)")
    print(f"    Equity Multiple: {fin.equity_multiple:.2f}x" if fin.equity_multiple else "    Equity Multiple: (not found)")
    print(f"    Cash-on-Cash: {fin.cash_on_cash_return:.1%}" if fin.cash_on_cash_return else "    Cash-on-Cash: (not found)")

    print(f"\n[6] EXTRACTED DEAL TERMS:")
    terms = analysis.deal_terms
    print(f"    Loan Amount: ${terms.loan_amount:,.0f}" if terms.loan_amount else "    Loan Amount: (not found)")
    print(f"    LTV: {terms.loan_to_value:.1%}" if terms.loan_to_value else "    LTV: (not found)")
    print(f"    Interest Rate: {terms.interest_rate:.2%}" if terms.interest_rate else "    Interest Rate: (not found)")
    print(f"    Hold Period: {terms.hold_period_years} years" if terms.hold_period_years else "    Hold Period: (not found)")
    print(f"    Preferred Return: {terms.preferred_return:.1%}" if terms.preferred_return else "    Preferred Return: (not found)")
    print(f"    Profit Split: {terms.profit_split or '(not found)'}")

    print(f"\n[7] EXTRACTED FEES:")
    fees = analysis.fees
    print(f"    Acquisition Fee: {fees.acquisition_fee:.1%}" if fees.acquisition_fee else "    Acquisition Fee: (not found)")
    print(f"    Asset Mgmt Fee: {fees.asset_management_fee:.1%}" if fees.asset_management_fee else "    Asset Mgmt Fee: (not found)")
    print(f"    Property Mgmt Fee: {fees.property_management_fee:.1%}" if fees.property_management_fee else "    Property Mgmt Fee: (not found)")
    print(f"    Disposition Fee: {fees.disposition_fee:.1%}" if fees.disposition_fee else "    Disposition Fee: (not found)")

    print(f"\n[8] EXTRACTED MARKET DATA:")
    market = analysis.market_data
    print(f"    Market Vacancy: {market.market_vacancy_rate:.1%}" if market.market_vacancy_rate else "    Market Vacancy: (not found)")
    print(f"    Market Rent PSF: ${market.market_rent_psf:.2f}" if market.market_rent_psf else "    Market Rent PSF: (not found)")
    print(f"    Market Cap Rate: {market.market_cap_rate:.2%}" if market.market_cap_rate else "    Market Cap Rate: (not found)")
    print(f"    Rent Growth: {market.rent_growth_1yr:.1%}" if market.rent_growth_1yr else "    Rent Growth: (not found)")

    # Step 5: Search for key terms in raw text
    print(f"\n[9] SEARCHING FOR KEY TERMS IN RAW TEXT:")
    search_terms = [
        'price', 'purchase', 'cap rate', 'noi', 'units', 'occupancy',
        'rent', 'irr', 'equity multiple', 'preferred', 'fee', 'loan',
        'walt', 'lease term', 'vacancy', 'year built', 'built between', 'tenants'
    ]
    text_lower = raw_text.lower()
    for term in search_terms:
        count = text_lower.count(term)
        if count > 0:
            # Find first occurrence with context
            idx = text_lower.find(term)
            context = raw_text[max(0, idx-20):min(len(raw_text), idx+50)]
            context = context.replace('\n', ' ').strip()
            print(f"    '{term}': found {count}x - e.g., '...{context}...'")
        else:
            print(f"    '{term}': NOT FOUND")

    # Save raw text for inspection
    output_file = Path(file_path).stem + "_extracted.txt"
    with open(output_file, 'w') as f:
        f.write(raw_text)
    print(f"\n[10] Full extracted text saved to: {output_file}")
    print(f"\nReview this file to see exactly what text was extracted from the PDF.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 diagnose_pdf.py <path_to_pdf>")
        sys.exit(1)

    diagnose_pdf(sys.argv[1])
