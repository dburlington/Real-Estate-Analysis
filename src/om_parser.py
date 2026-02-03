"""OM Parser - Extracts deal information from Offering Memorandums"""
from __future__ import annotations

import re
import io
import subprocess
from pathlib import Path
from typing import Optional, List, Tuple
from .models import (
    PropertyDetails, FinancialMetrics, DealTerms, SponsorFees,
    PropertyType, OMAnalysis, MarketData
)

# Try to import PDF libraries with fallbacks
PDF_LIBS = {}

try:
    import pdfplumber
    PDF_LIBS['pdfplumber'] = True
except ImportError:
    PDF_LIBS['pdfplumber'] = False

try:
    import fitz  # PyMuPDF
    PDF_LIBS['pymupdf'] = True
except ImportError:
    PDF_LIBS['pymupdf'] = False

try:
    import PyPDF2
    PDF_LIBS['pypdf2'] = True
except ImportError:
    PDF_LIBS['pypdf2'] = False

# Check for OCR support
try:
    import pytesseract
    from PIL import Image
    PDF_LIBS['tesseract'] = True
except ImportError:
    PDF_LIBS['tesseract'] = False

PDF_SUPPORT = any([PDF_LIBS.get('pymupdf'), PDF_LIBS.get('pdfplumber'), PDF_LIBS.get('pypdf2')])


class PDFExtractor:
    """Multi-backend PDF text extractor with OCR fallback for scanned documents"""

    def __init__(self):
        self.extraction_method = None
        self.errors = []
        self.is_scanned = False

    def extract(self, file_path: str) -> str:
        """Extract text from PDF using best available method, with OCR fallback"""
        text = ""
        self.errors = []
        self.is_scanned = False

        # Try text-based extraction first
        text = self._try_text_extraction(file_path)

        if self._is_valid_extraction(text):
            return text

        # Text extraction failed - likely a scanned PDF
        print("Standard text extraction failed. Attempting OCR...")
        self.is_scanned = True

        # Try OCR extraction
        text = self._try_ocr_extraction(file_path)

        if self._is_valid_extraction(text):
            return text

        # If we got some text but it didn't validate, return it anyway with a warning
        if text and len(text) > 50:
            print(f"Warning: Extracted text may be incomplete ({len(text)} chars)")
            return text

        # Complete failure
        raise ValueError(
            f"Failed to extract text from PDF.\n"
            f"This appears to be a scanned PDF that requires OCR.\n"
            f"Errors: {'; '.join(self.errors)}\n"
            f"Available libraries: {PDF_LIBS}\n\n"
            f"To enable OCR, install: pip install pytesseract pillow\n"
            f"And install Tesseract: brew install tesseract (Mac) or apt install tesseract-ocr (Linux)"
        )

    def _try_text_extraction(self, file_path: str) -> str:
        """Try all text-based extraction methods"""
        text = ""

        # Try PyMuPDF first (best for complex layouts)
        if PDF_LIBS.get('pymupdf'):
            try:
                text = self._extract_with_pymupdf(file_path)
                if self._is_valid_extraction(text):
                    self.extraction_method = 'pymupdf'
                    return text
                else:
                    self.errors.append(f"PyMuPDF: only extracted {len(text)} chars")
            except Exception as e:
                self.errors.append(f"PyMuPDF error: {e}")

        # Try pdfplumber second (good for tables)
        if PDF_LIBS.get('pdfplumber'):
            try:
                text = self._extract_with_pdfplumber(file_path)
                if self._is_valid_extraction(text):
                    self.extraction_method = 'pdfplumber'
                    return text
                else:
                    self.errors.append(f"pdfplumber: only extracted {len(text)} chars")
            except Exception as e:
                self.errors.append(f"pdfplumber error: {e}")

        # Try PyPDF2 as last resort
        if PDF_LIBS.get('pypdf2'):
            try:
                text = self._extract_with_pypdf2(file_path)
                if self._is_valid_extraction(text):
                    self.extraction_method = 'pypdf2'
                    return text
                else:
                    self.errors.append(f"PyPDF2: only extracted {len(text)} chars")
            except Exception as e:
                self.errors.append(f"PyPDF2 error: {e}")

        return text

    def _try_ocr_extraction(self, file_path: str) -> str:
        """Try OCR-based extraction for scanned PDFs"""
        text = ""

        # Method 1: PyMuPDF with built-in OCR (if tesseract available)
        if PDF_LIBS.get('pymupdf'):
            try:
                text = self._extract_with_pymupdf_ocr(file_path)
                if self._is_valid_extraction(text):
                    self.extraction_method = 'pymupdf+ocr'
                    return text
            except Exception as e:
                self.errors.append(f"PyMuPDF OCR error: {e}")

        # Method 2: Convert to images and OCR with pytesseract
        if PDF_LIBS.get('tesseract') and PDF_LIBS.get('pymupdf'):
            try:
                text = self._extract_with_tesseract(file_path)
                if self._is_valid_extraction(text):
                    self.extraction_method = 'tesseract'
                    return text
            except Exception as e:
                self.errors.append(f"Tesseract error: {e}")

        return text

    def _extract_with_pymupdf(self, file_path: str) -> str:
        """Extract using PyMuPDF (fitz) - best for complex layouts"""
        doc = fitz.open(file_path)
        text_parts = []

        for page_num in range(len(doc)):
            page = doc[page_num]

            # Try multiple extraction methods and use the best result
            texts = []

            # Method 1: Simple text extraction
            try:
                simple_text = page.get_text("text")
                if simple_text:
                    texts.append(simple_text)
            except:
                pass

            # Method 2: Layout-preserving extraction
            try:
                layout_text = page.get_text("blocks")
                if layout_text:
                    block_texts = []
                    for block in layout_text:
                        if len(block) >= 5 and isinstance(block[4], str):
                            block_texts.append(block[4])
                    if block_texts:
                        texts.append("\n".join(block_texts))
            except:
                pass

            # Method 3: HTML extraction (sometimes works better)
            try:
                html_text = page.get_text("html")
                # Strip HTML tags
                clean_text = re.sub(r'<[^>]+>', ' ', html_text)
                clean_text = re.sub(r'\s+', ' ', clean_text)
                if len(clean_text) > 100:
                    texts.append(clean_text)
            except:
                pass

            # Use the longest extraction result
            if texts:
                best_text = max(texts, key=len)
                text_parts.append(best_text)

        doc.close()
        return "\n\n".join(text_parts)

    def _extract_with_pymupdf_ocr(self, file_path: str) -> str:
        """Extract using PyMuPDF's OCR capabilities"""
        doc = fitz.open(file_path)
        text_parts = []

        for page_num in range(len(doc)):
            page = doc[page_num]

            # Try to get OCR text using textpage with OCR
            try:
                # Render page to high-res image for OCR
                mat = fitz.Matrix(2.0, 2.0)  # 2x zoom for better OCR
                pix = page.get_pixmap(matrix=mat)

                # Try PyMuPDF's built-in OCR if available
                try:
                    tp = page.get_textpage_ocr(flags=fitz.TEXT_PRESERVE_WHITESPACE)
                    text = page.get_text("text", textpage=tp)
                    if text and len(text.strip()) > 20:
                        text_parts.append(text)
                        continue
                except:
                    pass

            except Exception as e:
                self.errors.append(f"OCR page {page_num} error: {e}")

        doc.close()
        return "\n\n".join(text_parts)

    def _extract_with_tesseract(self, file_path: str) -> str:
        """Extract using Tesseract OCR via pytesseract"""
        import pytesseract
        from PIL import Image

        doc = fitz.open(file_path)
        text_parts = []

        for page_num in range(len(doc)):
            page = doc[page_num]

            # Render page to image at high DPI for better OCR
            mat = fitz.Matrix(300/72, 300/72)  # 300 DPI
            pix = page.get_pixmap(matrix=mat)

            # Convert to PIL Image
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))

            # Run OCR
            try:
                text = pytesseract.image_to_string(img, config='--psm 1')
                if text:
                    text_parts.append(text)
            except Exception as e:
                self.errors.append(f"Tesseract page {page_num}: {e}")

        doc.close()
        return "\n\n".join(text_parts)

    def _extract_with_pdfplumber(self, file_path: str) -> str:
        """Extract using pdfplumber - good for tables"""
        text_parts = []

        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text_parts = []

                # Extract tables first
                try:
                    tables = page.extract_tables()
                    for table in tables:
                        if table:
                            for row in table:
                                if row:
                                    row_text = " | ".join(
                                        str(cell) if cell else "" for cell in row
                                    )
                                    if row_text.strip() and row_text.strip() != "|":
                                        page_text_parts.append(row_text)
                except:
                    pass

                # Extract regular text with layout preservation
                try:
                    text = page.extract_text(
                        layout=True,
                        x_tolerance=3,
                        y_tolerance=3
                    )
                    if text and len(text.strip()) > 10:
                        page_text_parts.append(text)
                except:
                    pass

                # If layout extraction failed, try without layout
                if not page_text_parts:
                    try:
                        text = page.extract_text()
                        if text and len(text.strip()) > 10:
                            page_text_parts.append(text)
                    except:
                        pass

                if page_text_parts:
                    text_parts.append("\n".join(page_text_parts))

        return "\n\n".join(text_parts)

    def _extract_with_pypdf2(self, file_path: str) -> str:
        """Extract using PyPDF2 - basic fallback"""
        text_parts = []

        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)

            for page in reader.pages:
                try:
                    text = page.extract_text()
                    if text:
                        # Clean up common PyPDF2 artifacts
                        text = re.sub(r'\s+', ' ', text)
                        text = re.sub(r'(\w)-\s+(\w)', r'\1\2', text)  # Fix hyphenation
                        text_parts.append(text)
                except:
                    pass

        return "\n\n".join(text_parts)

    def _is_valid_extraction(self, text: str) -> bool:
        """Check if extraction produced usable text"""
        if not text or len(text) < 200:
            return False

        # Remove non-printable characters for analysis
        printable_text = ''.join(c for c in text if c.isprintable() or c.isspace())

        # Check ratio of printable to total - scanned PDFs often have garbage chars
        if len(printable_text) < len(text) * 0.8:
            return False

        # Check for common OM keywords
        keywords = ['price', 'unit', 'property', 'investment', 'cap', 'noi', 'rent',
                   'income', 'expense', 'occupancy', 'sqft', 'square', 'building']
        text_lower = text.lower()
        matches = sum(1 for kw in keywords if kw in text_lower)

        return matches >= 2


class OMParser:
    """Parser for Real Estate Offering Memorandums"""

    # Regex patterns for extracting data
    PATTERNS = {
        # Property info - more flexible patterns
        'address': r'(?:address|location|property\s*address|site\s*address)[:\s]*([^\n,]+(?:,\s*[^\n]+)?)',
        'city_state_zip': r'([A-Za-z][A-Za-z\s]{2,30}),\s*([A-Z]{2})\s*(\d{5}(?:-\d{4})?)',
        'units': r'(?:total\s*)?(?:units?|apartment(?:s)?|doors?)[:\s]*(\d+)',
        'sqft': r'(?:total\s*)?(?:sf|sq\.?\s*ft\.?|square\s*feet|rsf|nsf|gsf)[:\s]*([\d,]+)',
        'year_built': r'(?:year\s*built|built\s*in|constructed|vintage)[:\s]*(\d{4})',
        'lot_size': r'(?:lot\s*size|land\s*area|acreage|site\s*size)[:\s]*([\d.]+)\s*(?:acres?|ac\.?|sf)?',

        # Financial metrics - expanded patterns
        'asking_price': r'(?:asking\s*price|list\s*price|offering\s*price|purchase\s*price|sale\s*price)[:\s]*\$?([\d,]+(?:\.\d+)?)\s*(?:M|MM|million)?',
        'price_per_unit': r'(?:price\s*per\s*unit|pp[uU]|per\s*unit)[:\s]*\$?([\d,]+(?:\.\d+)?)',
        'price_per_sqft': r'(?:price\s*per\s*(?:sf|sq\.?\s*ft\.?)|psf)[:\s]*\$?([\d,]+(?:\.\d+)?)',
        'cap_rate': r'(?:cap\s*rate|capitalization\s*rate|going[\s-]*in\s*cap)[:\s]*([\d.]+)\s*%?',
        'noi': r'(?:net\s*operating\s*income|noi|\bn\.o\.i\.)[:\s]*\$?([\d,]+(?:\.\d+)?)',
        'occupancy': r'(?:occupancy|occupied|physical\s*occupancy|economic\s*occupancy)[:\s]*([\d.]+)\s*%?',
        'avg_rent': r'(?:average\s*rent|avg\.?\s*rent|rent\s*per\s*unit|in[\s-]*place\s*rent)[:\s]*\$?([\d,]+(?:\.\d+)?)',
        'market_rent': r'(?:market\s*rent|achievable\s*rent)[:\s]*\$?([\d,]+(?:\.\d+)?)',
        'gpi': r'(?:gross\s*potential\s*income|gpi|gross\s*potential\s*rent|gpr)[:\s]*\$?([\d,]+(?:\.\d+)?)',
        'egi': r'(?:effective\s*gross\s*income|egi)[:\s]*\$?([\d,]+(?:\.\d+)?)',
        'expenses': r'(?:operating\s*expenses?|opex|total\s*expenses?)[:\s]*\$?([\d,]+(?:\.\d+)?)',
        'expense_ratio': r'(?:expense\s*ratio|operating\s*expense\s*ratio|oer)[:\s]*([\d.]+)\s*%?',
        'coc': r'(?:cash[\s-]*on[\s-]*cash|coc|cash\s*yield)[:\s]*([\d.]+)\s*%?',
        'irr': r'(?:irr|internal\s*rate\s*of\s*return|levered\s*irr)[:\s]*([\d.]+)\s*%?',
        'equity_multiple': r'(?:equity\s*multiple|em|moic)[:\s]*([\d.]+)\s*x?',

        # Loan terms - expanded
        'loan_amount': r'(?:loan\s*amount|debt|mortgage|senior\s*loan)[:\s]*\$?([\d,]+(?:\.\d+)?)\s*(?:M|MM|million)?',
        'ltv': r'(?:ltv|loan[\s-]*to[\s-]*value|leverage)[:\s]*([\d.]+)\s*%?',
        'interest_rate': r'(?:interest\s*rate|coupon|rate)[:\s]*([\d.]+)\s*%?',
        'loan_term': r'(?:loan\s*term|term|maturity)[:\s]*(\d+)\s*(?:years?|yrs?)?',
        'amortization': r'(?:amortization|amort\.?)[:\s]*(\d+)\s*(?:years?|yrs?)?',

        # Deal terms - expanded
        'min_investment': r'(?:minimum\s*investment|min\.?\s*invest(?:ment)?|minimum\s*equity)[:\s]*\$?([\d,]+(?:\.\d+)?)',
        'preferred_return': r'(?:preferred\s*return|pref(?:erred)?\.?\s*return|pref)[:\s]*([\d.]+)\s*%?',
        'profit_split': r'(?:profit\s*split|waterfall|split|promote)[:\s]*(\d+)\s*/\s*(\d+)',
        'hold_period': r'(?:hold\s*period|holding\s*period|investment\s*period|target\s*hold)[:\s]*(\d+)\s*(?:years?|yrs?)?',

        # Fee patterns
        'acquisition_fee': r'(?:acquisition\s*fee|acq\.?\s*fee|closing\s*fee)[:\s]*([\d.]+)\s*%?',
        'asset_management_fee': r'(?:asset\s*management\s*fee|am\s*fee|management\s*fee)[:\s]*([\d.]+)\s*%?',
        'property_management_fee': r'(?:property\s*management|pm\s*fee)[:\s]*([\d.]+)\s*%?',
        'construction_management_fee': r'(?:construction\s*management|cm\s*fee|development\s*fee)[:\s]*([\d.]+)\s*%?',
        'disposition_fee': r'(?:disposition\s*fee|disp\.?\s*fee|exit\s*fee|sale\s*fee)[:\s]*([\d.]+)\s*%?',
        'refinance_fee': r'(?:refinance\s*fee|refi\s*fee)[:\s]*([\d.]+)\s*%?',
        'financing_fee': r'(?:financing\s*fee|loan\s*fee|origination\s*fee)[:\s]*([\d.]+)\s*%?',
    }

    PROPERTY_TYPES = {
        'multifamily': PropertyType.MULTIFAMILY,
        'multi-family': PropertyType.MULTIFAMILY,
        'apartment': PropertyType.MULTIFAMILY,
        'residential': PropertyType.MULTIFAMILY,
        'garden style': PropertyType.MULTIFAMILY,
        'mid-rise': PropertyType.MULTIFAMILY,
        'high-rise': PropertyType.MULTIFAMILY,
        'office': PropertyType.OFFICE,
        'retail': PropertyType.RETAIL,
        'shopping': PropertyType.RETAIL,
        'strip center': PropertyType.RETAIL,
        'industrial': PropertyType.INDUSTRIAL,
        'warehouse': PropertyType.INDUSTRIAL,
        'logistics': PropertyType.INDUSTRIAL,
        'distribution': PropertyType.INDUSTRIAL,
        'flex': PropertyType.INDUSTRIAL,
        'mixed-use': PropertyType.MIXED_USE,
        'mixed use': PropertyType.MIXED_USE,
        'hotel': PropertyType.HOTEL,
        'hospitality': PropertyType.HOTEL,
        'self-storage': PropertyType.SELF_STORAGE,
        'storage': PropertyType.SELF_STORAGE,
        'senior': PropertyType.SENIOR_HOUSING,
        'assisted living': PropertyType.SENIOR_HOUSING,
        'student': PropertyType.STUDENT_HOUSING,
    }

    def __init__(self):
        self.raw_text = ""
        self.pdf_extractor = PDFExtractor()

    def parse_file(self, file_path: str) -> OMAnalysis:
        """Parse an OM from a file (PDF or text)"""
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if path.suffix.lower() == '.pdf':
            if not PDF_SUPPORT:
                available = [k for k, v in PDF_LIBS.items() if v]
                raise ImportError(
                    f"No PDF library available. Install one of: pip install pymupdf pdfplumber PyPDF2\n"
                    f"Recommended: pip install pymupdf (best quality)"
                )
            self.raw_text = self.pdf_extractor.extract(file_path)
            print(f"PDF extracted using: {self.pdf_extractor.extraction_method}")
            print(f"Extracted {len(self.raw_text)} characters")
        else:
            # Try multiple encodings for text files
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        self.raw_text = f.read()
                    break
                except UnicodeDecodeError:
                    continue

        if not self.raw_text:
            raise ValueError(f"Could not read content from: {file_path}")

        return self._parse_text(self.raw_text)

    def parse_text(self, text: str) -> OMAnalysis:
        """Parse an OM from raw text"""
        self.raw_text = text
        return self._parse_text(text)

    def _parse_text(self, text: str) -> OMAnalysis:
        """Parse text content and extract all deal information"""
        # Normalize text
        text = self._normalize_text(text)
        text_lower = text.lower()

        property_details = self._extract_property_details(text, text_lower)
        financials = self._extract_financials(text, text_lower)
        deal_terms = self._extract_deal_terms(text, text_lower)
        fees = self._extract_fees(text, text_lower)

        # Calculate derived metrics
        self._calculate_derived_metrics(financials, property_details)

        return OMAnalysis(
            property=property_details,
            financials=financials,
            deal_terms=deal_terms,
            fees=fees,
            market_data=MarketData(),
            raw_text=text
        )

    def _normalize_text(self, text: str) -> str:
        """Normalize extracted text for better parsing"""
        # Fix common PDF extraction issues
        text = re.sub(r'\x00', '', text)  # Remove null bytes
        text = re.sub(r'\r\n', '\n', text)  # Normalize line endings
        text = re.sub(r'\r', '\n', text)

        # Fix spacing issues from PDF extraction
        text = re.sub(r'(\d)\s+,\s*(\d)', r'\1,\2', text)  # Fix "1 , 000" -> "1,000"
        text = re.sub(r'\$\s+(\d)', r'$\1', text)  # Fix "$ 100" -> "$100"
        text = re.sub(r'(\d)\s*%', r'\1%', text)  # Fix "10 %" -> "10%"

        # Fix hyphenation from line breaks
        text = re.sub(r'(\w)-\s*\n\s*(\w)', r'\1\2', text)

        # Normalize multiple spaces but preserve line breaks
        text = re.sub(r'[^\S\n]+', ' ', text)

        # Normalize multiple line breaks
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text.strip()

    def _safe_float(self, value_str: str) -> Optional[float]:
        """Safely convert string to float, returning None on failure"""
        if not value_str:
            return None
        cleaned = value_str.replace(',', '').replace(' ', '').strip()
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return None

    def _extract_number(self, text: str, pattern: str, multiplier: float = 1.0) -> Optional[float]:
        """Extract a number using a regex pattern"""
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                value_str = match.group(1)
                value = self._safe_float(value_str)
                if value is None:
                    return None

                value *= multiplier

                # Check for million indicator in the match context
                context = text[match.start():min(match.end()+20, len(text))].lower()
                if any(m in context for m in ['million', ' m ', ' mm']):
                    if value < 1000:  # Likely already in millions notation
                        value *= 1_000_000

                return value
            except (ValueError, IndexError, AttributeError):
                pass
        return None

    def _extract_all_numbers(self, text: str, pattern: str) -> list[tuple[str, float]]:
        """Extract all matching numbers with their context"""
        results = []
        for match in re.finditer(pattern, text, re.IGNORECASE):
            try:
                context = text[max(0, match.start()-30):match.start()]
                value_str = match.group(1)
                value = self._safe_float(value_str)
                if value is not None:
                    results.append((context.lower(), value))
            except (ValueError, IndexError, AttributeError):
                pass
        return results

    def _extract_property_details(self, text: str, text_lower: str) -> PropertyDetails:
        """Extract property details from text"""
        details = PropertyDetails()

        # Extract property name (look for prominent headers or "Property:" labels)
        name_patterns = [
            r'(?:property\s*name|subject\s*property|project\s*name)[:\s]*([^\n]+)',
            r'^([A-Z][A-Za-z\s]+(?:Apartments|Place|Gardens|Manor|Village|Towers|Commons|Estates|Court|Park))',
        ]
        for pattern in name_patterns:
            name_match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
            if name_match:
                details.name = name_match.group(1).strip().title()
                break

        # Extract address - try multiple patterns
        address_patterns = [
            self.PATTERNS['address'],
            r'(\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Boulevard|Blvd|Road|Rd|Drive|Dr|Lane|Ln|Way|Circle|Cir)[^\n]*)',
        ]
        for pattern in address_patterns:
            address_match = re.search(pattern, text, re.IGNORECASE)
            if address_match:
                details.address = address_match.group(1).strip()
                break

        # Extract city, state, zip - try multiple patterns
        csz_patterns = [
            self.PATTERNS['city_state_zip'],
            r'([A-Za-z][A-Za-z\s]{2,20})\s*,\s*([A-Z]{2})\s*(\d{5})',
        ]
        for pattern in csz_patterns:
            csz_match = re.search(pattern, text)
            if csz_match:
                details.city = csz_match.group(1).strip()
                details.state = csz_match.group(2).upper()
                details.zip_code = csz_match.group(3)
                break

        # Extract property type
        for keyword, prop_type in self.PROPERTY_TYPES.items():
            if keyword in text_lower:
                details.property_type = prop_type
                break

        # Extract numeric details with validation
        units = self._extract_number(text, self.PATTERNS['units'])
        if units and 1 < units < 10000:  # Sanity check
            details.total_units = int(units)

        sqft = self._extract_number(text, self.PATTERNS['sqft'])
        if sqft and sqft > 100:  # Sanity check
            details.total_sqft = sqft

        year = self._extract_number(text, self.PATTERNS['year_built'])
        if year and 1800 < year < 2030:
            details.year_built = int(year)

        lot_size = self._extract_number(text, self.PATTERNS['lot_size'])
        if lot_size:
            details.lot_size_acres = lot_size

        # Extract amenities
        amenity_keywords = [
            'pool', 'gym', 'fitness', 'clubhouse', 'parking', 'garage',
            'laundry', 'playground', 'dog park', 'business center',
            'concierge', 'rooftop', 'balcony', 'patio', 'storage',
            'tennis', 'basketball', 'volleyball', 'grill', 'bbq',
            'theater', 'yoga', 'spa', 'sauna', 'package locker'
        ]
        details.amenities = [a for a in amenity_keywords if a in text_lower]

        return details

    def _extract_financials(self, text: str, text_lower: str) -> FinancialMetrics:
        """Extract financial metrics from text"""
        financials = FinancialMetrics()

        # Asking price - handle various formats
        price_patterns = [
            r'(?:asking\s*price|list\s*price|offering\s*price|purchase\s*price|sale\s*price)[:\s]*\$?([\d,]+(?:\.\d+)?)\s*(M|MM|million)?',
            r'(?:price|total\s*price)[:\s]*\$?([\d,]+(?:\.\d+)?)\s*(M|MM|million)?',
        ]
        for pattern in price_patterns:
            price_match = re.search(pattern, text, re.IGNORECASE)
            if price_match and price_match.group(1):
                price = self._safe_float(price_match.group(1))
                if price is not None:
                    if price_match.group(2) or price < 1000:
                        price *= 1_000_000
                    financials.asking_price = price
                    break

        financials.price_per_unit = self._extract_number(text, self.PATTERNS['price_per_unit'])
        financials.price_per_sqft = self._extract_number(text, self.PATTERNS['price_per_sqft'])

        # Cap rates - handle multiple cap rates with context
        cap_matches = re.findall(
            r'(?:(in[\s-]*place|current|going[\s-]*in|pro[\s-]*forma|stabilized|exit)\s+)?cap\s*rate[:\s]*([\d.]+)\s*%?',
            text, re.IGNORECASE
        )
        for prefix, rate in cap_matches:
            rate_val = self._safe_float(rate)
            if rate_val is None:
                continue
            if rate_val > 1:  # Convert from percentage
                rate_val /= 100
            if rate_val > 0.15 or rate_val < 0.01:  # Sanity check - cap rates typically 1-15%
                continue
            prefix_lower = (prefix or '').lower()
            if any(p in prefix_lower for p in ['pro', 'stabilized', 'exit']):
                financials.proforma_cap_rate = rate_val
            elif any(p in prefix_lower for p in ['current', 'in-place', 'in place', 'going']):
                financials.current_cap_rate = rate_val
            elif not financials.current_cap_rate:
                financials.current_cap_rate = rate_val

        # NOI - handle multiple with context
        noi_matches = re.findall(
            r'(?:(in[\s-]*place|current|t-?12|trailing|pro[\s-]*forma|stabilized|year\s*\d+)\s+)?(?:net\s*operating\s*income|noi)[:\s]*\$?([\d,]+)',
            text, re.IGNORECASE
        )
        for prefix, noi in noi_matches:
            noi_val = self._safe_float(noi)
            if noi_val is None:
                continue
            if noi_val < 1000:  # Likely in thousands
                noi_val *= 1000
            prefix_lower = (prefix or '').lower()
            if any(p in prefix_lower for p in ['pro', 'stabilized']):
                financials.proforma_noi = noi_val
            elif not financials.current_noi:
                financials.current_noi = noi_val

        # Occupancy - may appear multiple times
        occ_matches = self._extract_all_numbers(text, self.PATTERNS['occupancy'])
        for context, occ in occ_matches:
            if 'economic' not in context:  # Prefer physical occupancy
                occ_val = occ if occ <= 1 else occ / 100
                if 0.5 <= occ_val <= 1.0:  # Sanity check
                    financials.current_occupancy = occ_val
                    break

        financials.average_rent = self._extract_number(text, self.PATTERNS['avg_rent'])
        financials.market_rent = self._extract_number(text, self.PATTERNS['market_rent'])
        financials.gross_potential_income = self._extract_number(text, self.PATTERNS['gpi'])
        financials.effective_gross_income = self._extract_number(text, self.PATTERNS['egi'])
        financials.operating_expenses = self._extract_number(text, self.PATTERNS['expenses'])

        exp_ratio = self._extract_number(text, self.PATTERNS['expense_ratio'])
        if exp_ratio:
            exp_ratio_val = exp_ratio if exp_ratio <= 1 else exp_ratio / 100
            if 0.1 <= exp_ratio_val <= 0.9:  # Sanity check
                financials.expense_ratio = exp_ratio_val

        coc = self._extract_number(text, self.PATTERNS['coc'])
        if coc:
            coc_val = coc if coc <= 1 else coc / 100
            if 0 <= coc_val <= 0.5:  # Sanity check
                financials.cash_on_cash_return = coc_val

        irr = self._extract_number(text, self.PATTERNS['irr'])
        if irr:
            irr_val = irr if irr <= 1 else irr / 100
            if 0 <= irr_val <= 0.5:  # Sanity check
                financials.irr_projected = irr_val

        em = self._extract_number(text, self.PATTERNS['equity_multiple'])
        if em and 1.0 <= em <= 5.0:  # Sanity check
            financials.equity_multiple = em

        return financials

    def _extract_deal_terms(self, text: str, text_lower: str) -> DealTerms:
        """Extract deal terms from text"""
        terms = DealTerms()

        # Loan amount
        loan_patterns = [
            r'(?:loan\s*amount|senior\s*loan|debt\s*amount)[:\s]*\$?([\d,]+(?:\.\d+)?)\s*(M|MM|million)?',
            r'(?:mortgage|financing)[:\s]*\$?([\d,]+(?:\.\d+)?)\s*(M|MM|million)?',
        ]
        for pattern in loan_patterns:
            loan_match = re.search(pattern, text, re.IGNORECASE)
            if loan_match and loan_match.group(1):
                loan = self._safe_float(loan_match.group(1))
                if loan is not None:
                    if loan_match.group(2) or loan < 1000:
                        loan *= 1_000_000
                    terms.loan_amount = loan
                    break

        ltv = self._extract_number(text, self.PATTERNS['ltv'])
        if ltv:
            ltv_val = ltv if ltv <= 1 else ltv / 100
            if 0.3 <= ltv_val <= 0.95:  # Sanity check
                terms.loan_to_value = ltv_val

        rate = self._extract_number(text, self.PATTERNS['interest_rate'])
        if rate:
            rate_val = rate if rate <= 1 else rate / 100
            if 0.02 <= rate_val <= 0.15:  # Sanity check (2-15%)
                terms.interest_rate = rate_val

        loan_term = self._extract_number(text, self.PATTERNS['loan_term'])
        if loan_term and 1 <= loan_term <= 40:
            terms.loan_term_years = int(loan_term)

        amort = self._extract_number(text, self.PATTERNS['amortization'])
        if amort and 5 <= amort <= 40:
            terms.amortization_years = int(amort)

        # Loan type detection - more patterns
        if any(x in text_lower for x in ['fixed rate', 'fixed-rate']):
            terms.loan_type = 'Fixed'
        elif any(x in text_lower for x in ['variable', 'floating', 'adjustable', 'sofr', 'libor']):
            terms.loan_type = 'Variable'
        elif 'bridge' in text_lower:
            terms.loan_type = 'Bridge'
        elif 'construction' in text_lower:
            terms.loan_type = 'Construction'

        terms.assumable_debt = any(x in text_lower for x in ['assumable', 'assumption'])

        terms.minimum_investment = self._extract_number(text, self.PATTERNS['min_investment'])

        pref = self._extract_number(text, self.PATTERNS['preferred_return'])
        if pref:
            pref_val = pref if pref <= 1 else pref / 100
            if 0 <= pref_val <= 0.15:
                terms.preferred_return = pref_val

        split_match = re.search(self.PATTERNS['profit_split'], text, re.IGNORECASE)
        if split_match:
            terms.profit_split = f"{split_match.group(1)}/{split_match.group(2)}"

        hold = self._extract_number(text, self.PATTERNS['hold_period'])
        if hold and 1 <= hold <= 15:
            terms.hold_period_years = int(hold)

        # Prepayment penalty
        prepay_patterns = [
            r'prepay(?:ment)?\s*(?:penalty)?[:\s]*([^\n.]{5,50})',
            r'yield\s*maintenance',
            r'defeasance',
        ]
        for pattern in prepay_patterns:
            prepay_match = re.search(pattern, text, re.IGNORECASE)
            if prepay_match:
                if prepay_match.lastindex:
                    terms.prepayment_penalty = prepay_match.group(1).strip()
                else:
                    terms.prepayment_penalty = prepay_match.group(0).strip()
                break

        return terms

    def _parse_fee_percentage(self, value: Optional[float]) -> Optional[float]:
        """Convert a fee value to a decimal percentage.

        Fee percentages in OMs are typically written as:
        - "1.0%" or "1%" meaning 0.01 (1 percent)
        - "2.5%" meaning 0.025 (2.5 percent)
        - "10%" meaning 0.10 (10 percent)

        This method converts any reasonable fee value to a decimal.
        """
        if value is None:
            return None

        # Fees are almost never > 20%, so if we see a number > 0.20,
        # it's likely expressed as a percentage (e.g., 1.5 = 1.5%)
        if value > 0.20:
            return value / 100

        # If it's between 0.01 and 0.20, it could be either:
        # - Already a decimal (e.g., 0.015 = 1.5%)
        # - A small percentage number (e.g., 1.5 = 1.5%)
        # We'll assume values >= 0.5 are percentages
        if value >= 0.5:
            return value / 100

        # Otherwise it's already a decimal
        return value

    def _extract_fees(self, text: str, text_lower: str) -> SponsorFees:
        """Extract sponsor/GP fee structure from text"""
        fees = SponsorFees()

        # Acquisition fee
        acq_fee = self._extract_number(text, self.PATTERNS['acquisition_fee'])
        fees.acquisition_fee = self._parse_fee_percentage(acq_fee)

        # Also look for flat acquisition fee
        acq_flat_match = re.search(
            r'(?:acquisition\s*fee|acq\.?\s*fee)[:\s]*\$?([\d,]+(?:\.\d+)?)\s*(?:K|thousand)?',
            text, re.IGNORECASE
        )
        if acq_flat_match:
            flat_val = self._safe_float(acq_flat_match.group(1))
            if flat_val and flat_val > 100:  # Likely a flat dollar amount
                fees.acquisition_fee_flat = flat_val

        # Asset management fee
        am_fee = self._extract_number(text, self.PATTERNS['asset_management_fee'])
        fees.asset_management_fee = self._parse_fee_percentage(am_fee)

        # Property management fee
        pm_fee = self._extract_number(text, self.PATTERNS['property_management_fee'])
        fees.property_management_fee = self._parse_fee_percentage(pm_fee)

        # Construction/development management fee
        cm_fee = self._extract_number(text, self.PATTERNS['construction_management_fee'])
        fees.construction_management_fee = self._parse_fee_percentage(cm_fee)

        # Disposition fee
        disp_fee = self._extract_number(text, self.PATTERNS['disposition_fee'])
        fees.disposition_fee = self._parse_fee_percentage(disp_fee)

        # Refinance fee
        refi_fee = self._extract_number(text, self.PATTERNS['refinance_fee'])
        fees.refinance_fee = self._parse_fee_percentage(refi_fee)

        # Financing/origination fee
        fin_fee = self._extract_number(text, self.PATTERNS['financing_fee'])
        fees.financing_fee = self._parse_fee_percentage(fin_fee)

        # Look for promote/waterfall tiers
        promote_patterns = [
            r'(\d+)\s*%\s*(?:promote|carried\s*interest|carry)\s*(?:above|after|over)\s*(\d+)\s*%\s*(?:irr|return)',
            r'(?:promote|carried\s*interest|carry)[:\s]*(\d+)\s*%\s*(?:above|after)\s*(\d+)\s*%',
            r'(\d+)\s*/\s*(\d+)\s*(?:split|waterfall)\s*(?:above|after)\s*(\d+)\s*%',
        ]
        for pattern in promote_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if not fees.promote_tier_1:
                    fees.promote_tier_1 = match.group(0).strip()
                elif not fees.promote_tier_2:
                    fees.promote_tier_2 = match.group(0).strip()

        # Look for additional fee mentions
        other_fee_patterns = [
            (r'(?:investor\s*servicing|servicing\s*fee)[:\s]*([\d.]+)\s*%?', 'Investor Servicing'),
            (r'(?:organizational|org\.?\s*fee|formation\s*fee)[:\s]*([\d.]+)\s*%?', 'Organization Fee'),
            (r'(?:guarantee\s*fee|guaranty\s*fee)[:\s]*([\d.]+)\s*%?', 'Guarantee Fee'),
        ]
        for pattern, name in other_fee_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                val = self._safe_float(match.group(1))
                val = self._parse_fee_percentage(val)
                if val:
                    fees.other_fees.append((name, val))

        return fees

    def _calculate_derived_metrics(self, financials: FinancialMetrics, property_details: PropertyDetails):
        """Calculate any derived metrics that weren't explicitly stated"""
        # Price per unit
        if not financials.price_per_unit and financials.asking_price and property_details.total_units:
            financials.price_per_unit = financials.asking_price / property_details.total_units

        # Price per sqft
        if not financials.price_per_sqft and financials.asking_price and property_details.total_sqft:
            financials.price_per_sqft = financials.asking_price / property_details.total_sqft

        # Cap rate from NOI and price
        if not financials.current_cap_rate and financials.current_noi and financials.asking_price:
            cap = financials.current_noi / financials.asking_price
            if 0.02 <= cap <= 0.15:
                financials.current_cap_rate = cap

        # Expense ratio
        if not financials.expense_ratio and financials.operating_expenses and financials.effective_gross_income:
            ratio = financials.operating_expenses / financials.effective_gross_income
            if 0.1 <= ratio <= 0.9:
                financials.expense_ratio = ratio

    def get_extraction_stats(self) -> dict:
        """Return statistics about the extraction"""
        return {
            'text_length': len(self.raw_text),
            'pdf_method': getattr(self.pdf_extractor, 'extraction_method', None),
            'pdf_errors': getattr(self.pdf_extractor, 'errors', []),
        }
