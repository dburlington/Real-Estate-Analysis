"""OM Parser - Extracts deal information from Offering Memorandums"""

import re
import io
import subprocess
from pathlib import Path
from typing import Optional
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
        'address': r'(?:address|location|property\s*address|site\s*address|located\s*at)[:\s]*([^\n,]+(?:,\s*[^\n]+)?)',
        'city_state_zip': r'([A-Za-z][A-Za-z\s]{2,30}),\s*([A-Z]{2})\s*(\d{5}(?:-\d{4})?)',
        'units': r'(?:total\s*)?(?:units?|apartment(?:s)?|doors?)[:\s]*(\d+)',
        'sqft': r'([\d,]+)[\s-]*(?:sf|sq\.?\s*ft\.?|square[\s-]*foot|square\s*feet|rsf|nsf|gsf)',
        'year_built': r'(?:year\s*built|built\s*in|constructed|vintage|built\s*between)[:\s]*(\d{4})',
        'lot_size': r'(?:lot\s*size|land\s*area|acreage|site\s*size|spanning)[:\s]*([\d.]+)\s*(?:acres?|ac\.?|sf)?',

        # Financial metrics - expanded patterns for various OM formats
        'asking_price': r'(?:asking\s*price|list\s*price|offering\s*price|purchase\s*price|sale\s*price|total\s*price)[:\s]*\$?([\d,]+(?:\.\d+)?)\s*(?:M|MM|million)?',
        'price_per_unit': r'(?:price\s*per\s*unit|pp[uU]|per\s*unit)[:\s]*\$?([\d,]+(?:\.\d+)?)',
        'price_per_sqft': r'(?:price\s*per\s*(?:sf|sq\.?\s*ft\.?)|psf|sales?\s*price\s*psf)[:\s]*\$?([\d,]+(?:\.\d+)?)',
        'cap_rate': r'(?:cap\s*rate|capitalization\s*rate|going[\s-]*in\s*(?:cap|yield)|exit\s*cap(?:\s*rate)?)[:\s]*([\d.]+)\s*%?',
        'noi': r'(?:net\s*operating\s*income|noi|\bn\.o\.i\.)[:\s]*\$?([\d,]+(?:\.\d+)?)',
        'occupancy': r'(?:occupancy|occupied|physical\s*occupancy|economic\s*occupancy|fully\s*occupied)[:\s]*([\d.]+)\s*%?',
        'avg_rent': r'(?:average\s*rent|avg\.?\s*rent|rent\s*per\s*unit|in[\s-]*place\s*rent|market\s*rent)[:\s]*\$?([\d.]+)',
        'market_rent': r'(?:market\s*rent|achievable\s*rent|psf\s*market\s*rent)[:\s]*\$?([\d.]+)',
        'gpi': r'(?:gross\s*potential\s*income|gpi|gross\s*potential\s*rent|gpr)[:\s]*\$?([\d,]+(?:\.\d+)?)',
        'egi': r'(?:effective\s*gross\s*income|egi)[:\s]*\$?([\d,]+(?:\.\d+)?)',
        'expenses': r'(?:operating\s*expenses?|opex|total\s*expenses?)[:\s]*\$?([\d,]+(?:\.\d+)?)',
        'expense_ratio': r'(?:expense\s*ratio|operating\s*expense\s*ratio|oer)[:\s]*([\d.]+)\s*%?',
        'coc': r'(?:cash[\s-]*on[\s-]*cash|coc|cash\s*yield|annual\s*cash[\s-]*on[\s-]*cash)[:\s]*([\d.]+)\s*%?',
        'irr': r'(?:(?:net\s*)?irr|internal\s*rate\s*of\s*return|levered\s*irr|proforma\s*(?:net\s*)?irr)[:\s]*([\d.]+)\s*%?',
        'equity_multiple': r'(?:(?:net\s*)?equity\s*multiple|em|moic|proforma\s*(?:net\s*)?equity\s*multiple)[:\s]*([\d.]+)\s*x?',

        # Loan terms - expanded
        'loan_amount': r'(?:loan\s*amount|senior\s*debt|mortgage|senior\s*loan)[:\s]*\$?([\d,]+(?:\.\d+)?)\s*(?:M|MM|million)?',
        'ltv': r'(?:ltv|loan[\s-]*to[\s-]*value|leverage)[:\s]*([\d.]+)\s*%?',
        'interest_rate': r'(?:interest\s*rate|coupon|rate)[:\s]*([\d.]+)\s*%?',
        'loan_term': r'(?:loan\s*term|term|maturity)[:\s]*(\d+)\s*(?:years?|yrs?)?',
        'amortization': r'(?:amortization|amort\.?)[:\s]*(\d+)\s*(?:years?|yrs?)?',

        # Deal terms - expanded for syndication OMs
        'min_investment': r'(?:minimum\s*investment(?:\s*amount)?|min\.?\s*invest(?:ment)?|minimum\s*equity|minimum\s*capital\s*contribution)[:\s]*\$?([\d,]+(?:\.\d+)?)',
        'preferred_return': r'(?:preferred\s*return|pref(?:erred)?\.?\s*return|pref|irr\s*hurdle)[:\s]*([\d.]+)\s*%?',
        'profit_split': r'(?:profit\s*split|waterfall|split|promote)[:\s]*(\d+)\s*/\s*(\d+)',
        'hold_period': r'(?:hold\s*period|holding\s*period|investment\s*period|target\s*hold|estimated\s*duration)[:\s]*(\d+)\s*(?:years?|yrs?|months?)?',

        # Fee patterns - more flexible
        'acquisition_fee': r'(?:acquisition\s*fee|acq\.?\s*fee|closing\s*fee)[:\s]*([\d.]+)\s*%',
        'asset_management_fee': r'(?:(?:annual\s*)?asset\s*management\s*fee|am\s*fee)[:\s]*([\d.]+)\s*%',
        'property_management_fee': r'(?:property\s*management(?:\s*fee)?|pm\s*fee)[:\s]*([\d.]+)\s*%',
        'construction_management_fee': r'(?:construction\s*management(?:\s*fee)?|cm\s*fee|development\s*fee)[:\s]*([\d.]+)\s*%',
        'disposition_fee': r'(?:disposition\s*fee|disp\.?\s*fee|exit\s*fee|sale\s*fee|liquidation\s*fee)[:\s]*([\d.]+|none)\s*%?',
        'refinance_fee': r'(?:refinance\s*fee|refi\s*fee)[:\s]*([\d.]+)\s*%?',
        'financing_fee': r'(?:financing\s*fee|loan\s*fee|origination\s*fee|debt\s*broker\s*fee)[:\s]*([\d.]+)\s*%?',
    }

    # Property types ordered by specificity - more specific types first
    # This ensures "industrial" is detected before generic terms like "residential"
    PROPERTY_TYPE_KEYWORDS = [
        # Industrial - check first (most specific)
        ('industrial', PropertyType.INDUSTRIAL),
        ('warehouse', PropertyType.INDUSTRIAL),
        ('distribution', PropertyType.INDUSTRIAL),
        ('logistics', PropertyType.INDUSTRIAL),
        ('manufacturing', PropertyType.INDUSTRIAL),
        ('flex space', PropertyType.INDUSTRIAL),
        # Self-storage
        ('self-storage', PropertyType.SELF_STORAGE),
        ('self storage', PropertyType.SELF_STORAGE),
        # Hotel/Hospitality
        ('hotel', PropertyType.HOTEL),
        ('hospitality', PropertyType.HOTEL),
        ('motel', PropertyType.HOTEL),
        # Senior Housing
        ('senior housing', PropertyType.SENIOR_HOUSING),
        ('assisted living', PropertyType.SENIOR_HOUSING),
        ('memory care', PropertyType.SENIOR_HOUSING),
        # Student Housing
        ('student housing', PropertyType.STUDENT_HOUSING),
        ('student apartment', PropertyType.STUDENT_HOUSING),
        # Mixed Use
        ('mixed-use', PropertyType.MIXED_USE),
        ('mixed use', PropertyType.MIXED_USE),
        # Office
        ('office', PropertyType.OFFICE),
        ('office building', PropertyType.OFFICE),
        # Retail
        ('retail', PropertyType.RETAIL),
        ('shopping', PropertyType.RETAIL),
        ('strip center', PropertyType.RETAIL),
        ('shopping center', PropertyType.RETAIL),
        # Multifamily - check last (most generic)
        ('multifamily', PropertyType.MULTIFAMILY),
        ('multi-family', PropertyType.MULTIFAMILY),
        ('apartment', PropertyType.MULTIFAMILY),
        ('garden style', PropertyType.MULTIFAMILY),
        ('mid-rise', PropertyType.MULTIFAMILY),
        ('high-rise', PropertyType.MULTIFAMILY),
    ]

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
        market_data = self._extract_market_data(text, text_lower)

        # Calculate derived metrics
        self._calculate_derived_metrics(financials, property_details)

        return OMAnalysis(
            property=property_details,
            financials=financials,
            deal_terms=deal_terms,
            fees=fees,
            market_data=market_data,
            raw_text=text
        )

    def _normalize_text(self, text: str) -> str:
        """Normalize extracted text for better parsing"""
        # Fix common PDF extraction issues
        text = re.sub(r'\x00', '', text)  # Remove null bytes
        text = re.sub(r'\r\n', '\n', text)  # Normalize line endings
        text = re.sub(r'\r', '\n', text)

        # Decode HTML entities (common in PDF extraction)
        html_entities = {
            '&#x201c;': '"', '&#x201d;': '"',  # Smart quotes
            '&#x2018;': "'", '&#x2019;': "'",  # Smart apostrophes
            '&#x2013;': '-', '&#x2014;': '-',  # En-dash, em-dash
            '&#x2022;': '•', '&#x00b7;': '·',  # Bullets
            '&amp;': '&', '&lt;': '<', '&gt;': '>',
            '&nbsp;': ' ', '&#160;': ' ',
            '&quot;': '"', '&#34;': '"',
            '&apos;': "'", '&#39;': "'",
        }
        for entity, char in html_entities.items():
            text = text.replace(entity, char)
        # Also handle numeric HTML entities
        text = re.sub(r'&#x([0-9a-fA-F]+);', lambda m: chr(int(m.group(1), 16)), text)
        text = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), text)

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

        # Remove common legal boilerplate language from OMs
        text = self._remove_boilerplate(text)

        return text.strip()

    def _remove_boilerplate(self, text: str) -> str:
        """Remove common legal disclaimer boilerplate from OM text"""
        # Patterns for legal disclaimer sections to remove
        boilerplate_patterns = [
            # Investment disclaimer language
            r'(?i)(?:should|shall|could)\s+not\s+be\s+assumed\s+that\s+any\s+investment.*?(?:profitable|profitability)\.?',
            r'(?i)information\s+and\s+trends\s+this\s+document\s+contains.*?(?:accuracy\s+of\s+such\s+information|independently\s+verified)\.?',
            r'(?i)there\s+are\s+no\s+guarantees\s+that\s+any\s+of\s+the\s+trends.*?(?:future\s+events|future\s+results)\.?',
            r'(?i)past\s+events\s+and\s+trends\s+do\s+not\s+imply.*?(?:future\s+events|future\s+results)\.?',
            r'(?i)opinions?\s+expressed\s+in\s+this\s+document.*?(?:date\s+appearing|current\s+opinions?).*?(?:materials\s+only|subject\s+to\s+change)\.?',
            r'(?i)(?:series\s+)?investors?,?\s+financial\s+professionals?,?\s+and\s+prospective\s+investors?\s+should\s+not\s+rely\s+solely.*?(?:investment\s+decision|offering\s+memorandum)\.?',
            r'(?i)they\s+should\s+review\s+the\s+most\s+recent\s+offering\s*memorandum.*?(?:upon\s+request|subject\s+investment)\.?',
            r'(?i)copies\s+may\s+be\s+obtained\s+upon\s+request.*?\.?',
            r'(?i)certain\s+information\s+contained\s+in\s+(?:the|this)\s+materials?\s+discusses\s+general\s+market.*?',
            # Forward-looking statements
            r'(?i)forward[- ]looking\s+statements?.*?(?:actual\s+results|no\s+assurance).*?\.?',
            r'(?i)(?:this|the)\s+(?:document|memorandum|materials?)\s+(?:contains?|includes?)\s+(?:certain\s+)?(?:forward[- ]looking|projections?).*?\.?',
            # Not an offer language
            r'(?i)(?:this|the)\s+(?:document|memorandum|materials?)\s+(?:is|does)\s+not\s+(?:constitute|represent)\s+(?:an?\s+)?(?:offer|solicitation).*?\.?',
            r'(?i)no\s+(?:offer|representation|warranty).*?(?:is\s+made|being\s+made).*?\.?',
            # Confidentiality notices
            r'(?i)(?:this|the)\s+(?:document|memorandum|materials?)\s+(?:is|are)\s+(?:strictly\s+)?confidential.*?\.?',
            r'(?i)(?:for|intended\s+for)\s+(?:the\s+)?(?:sole|exclusive)\s+use\s+of.*?\.?',
            # General liability disclaimers
            r'(?i)(?:the\s+)?(?:sponsor|company|issuer|series)\s+(?:and\s+its\s+)?affiliates?\s+(?:do\s+not|does\s+not)\s+accept\s+any\s+responsibility.*?\.?',
            r'(?i)(?:no\s+)?(?:guarantee|warranty|representation)\s+(?:is\s+made|expressed|implied).*?(?:accuracy|completeness).*?\.?',
        ]

        for pattern in boilerplate_patterns:
            text = re.sub(pattern, '', text, flags=re.DOTALL)

        # Clean up any resulting multiple spaces or blank lines
        text = re.sub(r'[^\S\n]+', ' ', text)
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)

        return text

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
            # Match "OF PROPERTY_NAME" pattern common in investment memorandums
            r'INVESTMENT\s+MEMORANDUM\s+OF\s+([A-Z][A-Z\s]+(?:INDUSTRIAL|APARTMENTS|PARK|PLAZA|CENTER|PLACE))',
            # Match property names with common suffixes
            r'(?:the\s+)?["\']?([A-Z][A-Za-z\s]+(?:Industrial\s*Park|Apartments|Place|Gardens|Manor|Village|Towers|Commons|Estates|Court|Park|Plaza|Center))["\']?',
            r'^([A-Z][A-Za-z\s]+(?:Apartments|Place|Gardens|Manor|Village|Towers|Commons|Estates|Court|Park))',
        ]
        for pattern in name_patterns:
            name_match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
            if name_match:
                details.name = name_match.group(1).strip().title()
                break

        # Extract address - try multiple patterns including Highway
        address_patterns = [
            self.PATTERNS['address'],
            r'(\d+\s+[A-Za-z\s\.]+(?:Street|St|Avenue|Ave|Boulevard|Blvd|Road|Rd|Drive|Dr|Lane|Ln|Way|Circle|Cir|Highway|Hwy)[^\n]*)',
            r'located\s+at\s+(\d+[^\n,]+)',
        ]
        for pattern in address_patterns:
            address_match = re.search(pattern, text, re.IGNORECASE)
            if address_match:
                details.address = address_match.group(1).strip()
                break

        # Extract city, state - try multiple patterns including state names
        csz_patterns = [
            self.PATTERNS['city_state_zip'],
            r'([A-Za-z][A-Za-z\s]{2,20})\s*,\s*([A-Z]{2})\s*(\d{5})',
            # Match "City, State" without zip
            r'(?:in|of)\s+([A-Za-z][A-Za-z\s-]{2,25}),\s*([A-Z]{2})(?:\s|\.|\,)',
            # Match "Submarket of City-City, State"
            r'(?:Submarket|Market)\s+of\s+([A-Za-z][A-Za-z\s-]+),\s*([A-Za-z\s]+(?:Carolina|Virginia|Georgia|Texas|Florida|Arizona))',
        ]
        for pattern in csz_patterns:
            csz_match = re.search(pattern, text)
            if csz_match:
                details.city = csz_match.group(1).strip()
                state = csz_match.group(2).strip().upper()
                # Convert full state name to abbreviation
                state_abbrevs = {
                    'SOUTH CAROLINA': 'SC', 'NORTH CAROLINA': 'NC', 'VIRGINIA': 'VA',
                    'WEST VIRGINIA': 'WV', 'GEORGIA': 'GA', 'FLORIDA': 'FL',
                    'TEXAS': 'TX', 'ARIZONA': 'AZ', 'CALIFORNIA': 'CA',
                    'NEW YORK': 'NY', 'TENNESSEE': 'TN', 'ALABAMA': 'AL',
                }
                details.state = state_abbrevs.get(state, state[:2])
                if csz_match.lastindex >= 3:
                    details.zip_code = csz_match.group(3)
                break

        # Extract property type (keywords ordered by specificity - industrial before residential)
        for keyword, prop_type in self.PROPERTY_TYPE_KEYWORDS:
            if keyword in text_lower:
                details.property_type = prop_type
                break

        # Extract numeric details with validation
        units = self._extract_number(text, self.PATTERNS['units'])
        if units and 1 < units < 10000:  # Sanity check
            details.total_units = int(units)

        # Try multiple sqft patterns
        sqft_patterns = [
            r'([\d,]+)[\s-]*(?:sf|sq\.?\s*ft\.?|square[\s-]*foot|square\s*feet)',
            r'(?:rentable|total|gross)\s*(?:sf|square\s*feet)[:\s]*([\d,]+)',
            r'Total\s*/\s*Wtd\s*Avg[^\d]*([\d,]+)',  # From tables
        ]
        for pattern in sqft_patterns:
            sqft_match = re.search(pattern, text, re.IGNORECASE)
            if sqft_match:
                sqft = self._safe_float(sqft_match.group(1))
                if sqft and sqft > 1000:  # Sanity check for commercial
                    details.total_sqft = sqft
                    break

        year = self._extract_number(text, self.PATTERNS['year_built'])
        if year and 1800 < year < 2030:
            details.year_built = int(year)
        else:
            # Try "built between YYYY and YYYY" pattern
            year_range_match = re.search(r'built\s+between\s+(\d{4})\s+and\s+(\d{4})', text, re.IGNORECASE)
            if year_range_match:
                details.year_built = int(year_range_match.group(1))  # Use earliest year

        # Extract number of buildings
        buildings_patterns = [
            r'(\w+)[\s-]*building',  # "six-building" or "6 building"
            r'(\d+)\s*buildings?',
        ]
        word_to_num = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6,
                       'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12}
        for pattern in buildings_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                val = match.group(1).lower()
                if val.isdigit():
                    details.num_buildings = int(val)
                    # For industrial, buildings can serve as units
                    if not details.total_units and details.property_type == PropertyType.INDUSTRIAL:
                        details.total_units = int(val)
                elif val in word_to_num:
                    details.num_buildings = word_to_num[val]
                    if not details.total_units and details.property_type == PropertyType.INDUSTRIAL:
                        details.total_units = word_to_num[val]
                break

        # Extract WALT (Weighted Average Lease Term)
        walt_patterns = [
            r'([\d.]+)[\s-]*year\s+(?:weighted\s+average\s+)?(?:lease\s+term|walt)',
            r'(?:weighted\s+average\s+)?(?:lease\s+term|walt)[:\s]*([\d.]+)\s*(?:years?)?',
            r'walt\s*(?:of)?\s*([\d.]+)\s*(?:years?)?',
        ]
        for pattern in walt_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                walt = self._safe_float(match.group(1))
                if walt and 0.1 <= walt <= 30:  # Sanity check
                    details.walt_years = walt
                    break

        # Extract number of tenants
        tenant_patterns = [
            r'(?:fully\s+)?(?:occupied|leased)\s+(?:by|to)\s+(\w+)\s+tenants?',
            r'(\w+)\s+tenants?\s+(?:occupy|lease)',
            r'(\d+)\s+tenants?',
        ]
        for pattern in tenant_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                val = match.group(1).lower()
                if val.isdigit():
                    details.num_tenants = int(val)
                elif val in word_to_num:
                    details.num_tenants = word_to_num[val]
                break

        # Extract lot size - try multiple patterns
        lot_patterns = [
            r'(?:spanning|lot\s*size|land\s*area|site\s*size)[:\s]*([\d.]+)\s*(?:acres?|ac\.?)',
            r'([\d.]+)\s*acres?\s+(?:at|site|lot|property)',
        ]
        for pattern in lot_patterns:
            lot_match = re.search(pattern, text, re.IGNORECASE)
            if lot_match:
                lot_size = self._safe_float(lot_match.group(1))
                if lot_size and 0.1 < lot_size < 1000:
                    details.lot_size_acres = lot_size
                    break

        # Extract amenities / features based on property type
        if details.property_type == PropertyType.INDUSTRIAL:
            # Industrial property features
            amenity_keywords = [
                'dock doors', 'loading docks', 'drive-in doors', 'drive-in',
                'clear height', 'ceiling height', 'sprinkler', 'fire sprinkler',
                'hvac', 'climate controlled', 'led lighting', 'skylights',
                'trailer parking', 'truck court', 'rail access', 'rail served',
                'fenced yard', 'secured', 'gated', 'concrete floors',
                'heavy power', 'three phase', 'office space', 'mezzanine',
                'esfr', 'cross-dock', 'cold storage', 'freezer'
            ]
        elif details.property_type == PropertyType.OFFICE:
            amenity_keywords = [
                'parking', 'garage', 'conference', 'elevator', 'lobby',
                'fitness', 'gym', 'rooftop', 'terrace', 'cafe',
                'security', '24/7 access', 'fiber', 'backup power'
            ]
        elif details.property_type == PropertyType.RETAIL:
            amenity_keywords = [
                'parking', 'signage', 'pylon', 'drive-thru', 'drive-through',
                'pad site', 'anchor', 'outparcel', 'visibility'
            ]
        else:
            # Multifamily / residential amenities
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

        # Asking/Purchase price - handle various formats including tables
        price_patterns = [
            r'(?:asking\s*price|list\s*price|offering\s*price|purchase\s*price|sale\s*price)[:\s]*\$?([\d,]+(?:\.\d+)?)\s*(M|MM|million)?',
            r'Purchase\s*Price\s*\$?([\d,]+(?:\.\d+)?)',
            r'(?:price|total\s*price)[:\s]*\$?([\d,]+(?:\.\d+)?)\s*(M|MM|million)?',
        ]
        for pattern in price_patterns:
            price_match = re.search(pattern, text, re.IGNORECASE)
            if price_match and price_match.group(1):
                price = self._safe_float(price_match.group(1))
                if price is not None:
                    # Check for million suffix
                    has_million = price_match.lastindex >= 2 and price_match.group(2)
                    if has_million or price < 1000:
                        price *= 1_000_000
                    if price > 100000:  # Sanity check - at least $100k
                        financials.asking_price = price
                        break

        financials.price_per_unit = self._extract_number(text, self.PATTERNS['price_per_unit'])

        # Price per SF from market tables
        ppsf_patterns = [
            r'(?:sales?\s*price|price)\s*(?:psf|per\s*sf)[:\s]*\$?([\d,]+)',
            r'Sales\s*Price\s*PSF\s*\$?([\d,]+)',
        ]
        for pattern in ppsf_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                ppsf = self._safe_float(match.group(1))
                if ppsf and 10 < ppsf < 1000:
                    financials.price_per_sqft = ppsf
                    break

        # Cap rates - handle multiple cap rates with context
        # Look for "Projected Exit Cap Rate (4-year hold) 6.5%" or "Going-In Yield 6.3%"
        cap_patterns = [
            # Exit cap rate - with optional parenthetical
            (r'(?:projected\s*)?exit\s*cap(?:\s*rate)?(?:\s*\([^)]+\))?[:\s]*([\d.]+)\s*%?', 'exit'),
            # Going-in yield (current)
            (r'(?:proforma\s*)?going[\s-]*in\s*(?:cap|yield)[:\s]*([\d.]+)\s*%?', 'current'),
            # Stabilized yield (proforma)
            (r'(?:proforma\s*)?(?:stable|stabilized)(?:\s*year\s*\d+)?\s*yield(?:\s*on\s*cost)?[:\s]*([\d.]+)\s*%?', 'proforma'),
            # In-place / current cap
            (r'(?:in[\s-]*place|current)\s*(?:cap\s*rate|yield)[:\s]*([\d.]+)\s*%?', 'current'),
            # Generic cap rate
            (r'cap\s*rate[:\s]*([\d.]+)\s*%?', 'current'),
        ]
        for pattern, cap_type in cap_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                rate_val = self._safe_float(match.group(1))
                if rate_val is None:
                    continue
                if rate_val > 1:  # Convert from percentage
                    rate_val /= 100
                if 0.01 <= rate_val <= 0.15:  # Sanity check
                    if cap_type == 'exit' or cap_type == 'proforma':
                        if not financials.proforma_cap_rate:
                            financials.proforma_cap_rate = rate_val
                    elif cap_type == 'current':
                        if not financials.current_cap_rate:
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

        # Occupancy - check for "fully occupied" first
        if 'fully occupied' in text_lower or 'fully leased' in text_lower:
            financials.current_occupancy = 1.0
        else:
            occ_matches = self._extract_all_numbers(text, self.PATTERNS['occupancy'])
            for context, occ in occ_matches:
                if 'economic' not in context:  # Prefer physical occupancy
                    occ_val = occ if occ <= 1 else occ / 100
                    if 0.5 <= occ_val <= 1.0:  # Sanity check
                        financials.current_occupancy = occ_val
                        break

        # Market rent from tables (e.g., "PSF Market Rent $7.1")
        market_rent_patterns = [
            r'(?:psf\s*)?market\s*rent[:\s]*\$?([\d.]+)',
            r'market\s*rent\s*(?:psf)?[:\s]*\$?([\d.]+)',
        ]
        for pattern in market_rent_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                rent = self._safe_float(match.group(1))
                if rent and 1 < rent < 100:  # PSF rent sanity check
                    financials.market_rent = rent
                    break

        financials.average_rent = self._extract_number(text, self.PATTERNS['avg_rent'])
        if not financials.market_rent:
            financials.market_rent = self._extract_number(text, self.PATTERNS['market_rent'])
        financials.gross_potential_income = self._extract_number(text, self.PATTERNS['gpi'])
        financials.effective_gross_income = self._extract_number(text, self.PATTERNS['egi'])
        financials.operating_expenses = self._extract_number(text, self.PATTERNS['expenses'])

        exp_ratio = self._extract_number(text, self.PATTERNS['expense_ratio'])
        if exp_ratio:
            exp_ratio_val = exp_ratio if exp_ratio <= 1 else exp_ratio / 100
            if 0.1 <= exp_ratio_val <= 0.9:  # Sanity check
                financials.expense_ratio = exp_ratio_val

        # Cash on Cash - look for "Cash on Cash 7.7%", "Cash-on-Cash Return (Year 1): 2.1%", etc.
        coc_patterns = [
            # Value before label at start of string/line (check FIRST - most specific)
            r'(?:^|\n)\s*(\d+\.?\d*)\s*%\s*(?:average\s*)?(?:annual\s*)?cash[\s-]*on[\s-]*cash',
            # Label with optional "(Year X)" and explicit separator
            r'cash[\s-]*on[\s-]*cash(?:\s*return)?(?:\s*\([^)]+\))?\s*[:=]\s*(\d+\.?\d*)\s*%',
            # Label followed directly by value
            r'cash[\s-]*on[\s-]*cash\s+(\d+\.?\d*)\s*%',
        ]
        for pattern in coc_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                coc = self._safe_float(match.group(1))
                if coc:
                    coc_val = coc if coc <= 1 else coc / 100
                    if 0.02 <= coc_val <= 0.25:
                        financials.cash_on_cash_return = coc_val
                        break

        # IRR - look for "Total IRR 15.2%", "Target IRR 22%", etc.
        # IMPORTANT: Prioritize "Total/Net/Proforma/Target IRR" over plain "IRR" to avoid matching IRR hurdles
        # Note: \d* after IRR handles footnote superscripts like "IRR12" or "IRR^12" which get extracted as "IRR12"
        irr_patterns = [
            # Proforma Net IRR (with optional footnote number) - highest priority for projected returns
            r'proforma\s+(?:net\s+)?irr\d*\s*[:=]?\s*(\d+\.?\d*)\s*%',
            # Total/Net/Target IRR - these are the actual projected returns
            r'(?:total|net|target)\s+irr\d*\s*[:=]?\s*(\d+\.?\d*)\s*%',
            # Levered/Projected/Expected/Blended/LP/Investor/Unleveraged IRR
            r'(?:levered|projected|expected|estimated|blended|lp|investor|unlevered|unleveraged|deal|project|sponsor|series)\s+(?:investor\s+)?(?:net\s+)?irr\d*\s*[:=]?\s*(\d+\.?\d*)\s*%',
            # "Series Investor Net Returns" section followed by "Proforma Net IRR"
            r'(?:investor\s+)?(?:net\s+)?returns?\s*[\r\n]+\s*proforma\s+(?:net\s+)?irr\d*\s*(\d+\.?\d*)\s*%',
            # Value before "Total/Net/Target IRR"
            r'(\d+\.?\d*)\s*%\s*(?:total|net|target|projected|expected)\s+irr',
            # Internal rate of return (full phrase) - NOT hurdle
            r'internal\s+rate\s+of\s+return[^h]*?[:=]?\s*(\d+\.?\d*)\s*%',
            # IRR with parenthetical qualifier - "IRR (Projected): 15%", "IRR (Target): 18%"
            r'\birr\s*\([^)]+\)\s*[:=]?\s*(\d+\.?\d*)\s*%',
            # "IRR of 15.2%" format
            r'\birr\d*\s+of\s+(\d+\.?\d*)\s*%',
            # Yield patterns common in industrial/commercial OMs
            r'(?:unleveraged|unlevered|leveraged|levered|project|deal)\s+yield\d*\s*[:=]?\s*(\d+\.?\d*)\s*%',
            # Annual/annualized return patterns
            r'(?:annual|annualized|projected|target)\s+return\s*[:=]?\s*(\d+\.?\d*)\s*%',
            # IRR with footnote number then colon/equals - "IRR12: 15.2%"
            r'\birr\d+\s*[:=]?\s*(\d+\.?\d*)\s*%',
            # IRR with colon/equals (no footnote)
            r'\birr\s*[:=]\s*(\d+\.?\d*)\s*%',
            # IRR with dash separator - "IRR - 15.2%"
            r'\birr\d*\s*[-–—]\s*(\d+\.?\d*)\s*%',
            # IRR followed by space and value (no colon) - e.g., "IRR 15.2%"
            r'\birr\s+(\d+\.?\d*)\s*%',
            # Value before plain "IRR"
            r'(\d+\.?\d*)\s*%\s*\birr\b',
        ]
        for pattern in irr_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                irr = self._safe_float(match.group(1))
                if irr:
                    irr_val = irr if irr <= 1 else irr / 100
                    # IRR typically 6-35% for real estate (lowered min from 8% to 6%)
                    if 0.06 <= irr_val <= 0.35:
                        financials.irr_projected = irr_val
                        break

        # Equity Multiple - look for "Proforma Net Equity Multiple 1.7x"
        em_patterns = [
            r'(?:proforma\s*)?(?:net\s*)?equity\s*multiple[:\s]*([\d.]+)\s*x?',
            r'(?:net\s*)?equity\s*multiple(?:\s*\(\d+\))?[:\s]*([\d.]+)\s*x?',
            r'moic[:\s]*([\d.]+)\s*x?',
            # Additional patterns for commercial/industrial OMs
            r'(?:investment|return|total)\s*multiple[:\s]*([\d.]+)\s*x?',
            r'multiple\s*(?:of\s*)?(?:invested\s*)?(?:capital|equity)[:\s]*([\d.]+)\s*x?',
            r'\bmultiple\s*[:=]\s*([\d.]+)\s*x',
        ]
        for pattern in em_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                em = self._safe_float(match.group(1))
                if em and 1.0 <= em <= 5.0:
                    financials.equity_multiple = em
                    break

        return financials

    def _extract_deal_terms(self, text: str, text_lower: str) -> DealTerms:
        """Extract deal terms from text"""
        terms = DealTerms()

        # Loan/Debt amount - look for "Senior Debt $30,000,000"
        loan_patterns = [
            r'Senior\s*Debt\s*\$?([\d,]+)',
            r'(?:loan\s*amount|senior\s*loan|debt\s*amount)[:\s]*\$?([\d,]+(?:\.\d+)?)\s*(M|MM|million)?',
            r'(?:mortgage|financing)[:\s]*\$?([\d,]+(?:\.\d+)?)\s*(M|MM|million)?',
        ]
        for pattern in loan_patterns:
            loan_match = re.search(pattern, text, re.IGNORECASE)
            if loan_match and loan_match.group(1):
                loan = self._safe_float(loan_match.group(1))
                if loan is not None:
                    # Check for million suffix
                    has_million = loan_match.lastindex >= 2 and loan_match.group(2)
                    if has_million or loan < 1000:
                        loan *= 1_000_000
                    if loan > 100000:  # Sanity check
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

        # Minimum Investment - look for "Minimum Investment Amount $100,000"
        min_inv_patterns = [
            r'Minimum\s*Investment(?:\s*Amount)?[:\s]*\$?([\d,]+)',
            r'Minimum\s*Capital\s*Contribution[:\s]*\$?([\d,]+)',
            r'minimum\s*(?:investment|equity)[:\s]*\$?([\d,]+)',
        ]
        for pattern in min_inv_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                min_inv = self._safe_float(match.group(1))
                if min_inv and min_inv >= 1000:  # At least $1,000
                    terms.minimum_investment = min_inv
                    break

        # Preferred return / IRR Hurdle - look for "IRR Hurdle 6%", "6% hurdle", etc.
        # This is the minimum return LPs receive before the GP gets promote
        pref_patterns = [
            # Explicit IRR Hurdle patterns
            r'IRR\s*(?:Hurdle|Target)[:\s]*([\d.]+)\s*%',
            r'(?:Hurdle|Target)\s*IRR[:\s]*([\d.]+)\s*%',
            # Value before "hurdle" or "hurdle rate"
            r'([\d.]+)\s*%\s*(?:IRR\s*)?hurdle(?:\s*rate)?',
            # Hurdle rate of X%
            r'hurdle\s*(?:rate)?(?:\s*of)?[:\s]*([\d.]+)\s*%',
            # Preferred return patterns
            r'preferred\s*return[:\s]*([\d.]+)\s*%',
            r'pref(?:erred)?\s*(?:return)?[:\s]*([\d.]+)\s*%',
            r'([\d.]+)\s*%\s*pref(?:erred)?(?:\s*return)?',
            # Promote threshold patterns - "promote above 6%" means 6% is the pref
            r'promote\s*(?:above|over|after)[:\s]*([\d.]+)\s*%',
            r'([\d.]+)\s*%\s*(?:before|until)\s*promote',
            # General achieve IRR patterns
            r'(?:achieve\s*)?(?:an\s*)?IRR\s*(?:equal\s*to\s*)?([\d.]+)\s*(?:percent|%)',
        ]
        for pattern in pref_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                pref = self._safe_float(match.group(1))
                if pref:
                    pref_val = pref if pref <= 1 else pref / 100
                    # Pref return is typically 4-12%
                    if 0.04 <= pref_val <= 0.15:
                        terms.preferred_return = pref_val
                        break

        # Profit split - look for "eighty percent (80%) to the Series Member and twenty percent (20%)"
        split_patterns = [
            # "(80%) to the Series Member...and (20%) to the Manager"
            r'\((\d+)%?\)\s*to\s*(?:the\s*)?(?:Series\s*)?Member.*?\((\d+)%?\)\s*to\s*(?:the\s*)?Manager',
            # "80/20 split"
            r'(\d+)\s*/\s*(\d+)\s*(?:split|waterfall)',
            # General profit split pattern
            self.PATTERNS['profit_split'],
        ]
        for pattern in split_patterns:
            split_match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if split_match:
                terms.profit_split = f"{split_match.group(1)}/{split_match.group(2)}"
                break

        # Hold period - look for "Estimated Duration (Months) 48"
        hold_patterns = [
            r'Estimated\s*Duration\s*\(Months\)[:\s]*(\d+)',
            r'(?:hold|holding|investment)\s*period[:\s]*(\d+)\s*(?:months?|years?)',
            r'(\d+)\s*(?:months?|years?)\s*(?:hold|holding)\s*period',
            r'projected\s*holding\s*period\s*of\s*(\d+)\s*months',
        ]
        for pattern in hold_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                hold = self._safe_float(match.group(1))
                if hold:
                    # Check if it's months (typically > 12) or years
                    if 'month' in pattern.lower() or hold > 12:
                        hold = hold / 12  # Convert months to years
                    if 1 <= hold <= 15:
                        terms.hold_period_years = int(round(hold))
                        break

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

        # Acquisition fee - look for table format "Acquisition Fee ... 1.50%"
        acq_patterns = [
            r'Acquisition\s*Fee[:\s]*(?:.*?)([\d.]+)\s*%\s*(?:of\s*(?:the\s*)?Purchase\s*Price)?',
            r'(?:acquisition\s*fee|acq\.?\s*fee)[:\s]*([\d.]+)\s*%',
        ]
        for pattern in acq_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                acq_fee = self._safe_float(match.group(1))
                fees.acquisition_fee = self._parse_fee_percentage(acq_fee)
                break

        # Also look for flat acquisition fee
        acq_flat_match = re.search(
            r'(?:acquisition\s*fee|acq\.?\s*fee)[:\s]*\$?([\d,]+(?:\.\d+)?)\s*(?:K|thousand)?',
            text, re.IGNORECASE
        )
        if acq_flat_match:
            flat_val = self._safe_float(acq_flat_match.group(1))
            if flat_val and flat_val > 100:  # Likely a flat dollar amount
                fees.acquisition_fee_flat = flat_val

        # Asset management fee - look for "Annual Asset Management Fee 1.0%"
        am_patterns = [
            r'(?:Annual\s*)?Asset\s*Management\s*Fee[:\s]*([\d.]+)\s*%',
            r'(?:asset\s*management\s*fee|am\s*fee)[:\s]*([\d.]+)\s*%',
        ]
        for pattern in am_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                am_fee = self._safe_float(match.group(1))
                fees.asset_management_fee = self._parse_fee_percentage(am_fee)
                break

        # Property management fee
        pm_patterns = [
            r'Property\s*Management\s*(?:Fee)?[:\s]*([\d.]+)\s*%',
            r'(?:property\s*management|pm\s*fee)[:\s]*([\d.]+)\s*%',
        ]
        for pattern in pm_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                pm_fee = self._safe_float(match.group(1))
                fees.property_management_fee = self._parse_fee_percentage(pm_fee)
                break

        # Construction management fee - look for "Construction Management Fee 5.0%"
        cm_patterns = [
            r'Construction\s*Management\s*Fee[:\s]*([\d.]+)\s*%',
            r'(?:construction\s*management|cm\s*fee|development\s*fee)[:\s]*([\d.]+)\s*%',
        ]
        for pattern in cm_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                cm_fee = self._safe_float(match.group(1))
                fees.construction_management_fee = self._parse_fee_percentage(cm_fee)
                break

        # Disposition fee - check for "None" as well
        disp_patterns = [
            r'Disposition\s*Fee[:\s]*([\d.]+|None)\s*%?',
            r'(?:disposition\s*fee|exit\s*fee)[:\s]*([\d.]+|None)\s*%?',
        ]
        for pattern in disp_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                val = match.group(1)
                if val.lower() != 'none':
                    disp_fee = self._safe_float(val)
                    fees.disposition_fee = self._parse_fee_percentage(disp_fee)
                break

        # Refinance fee
        refi_fee = self._extract_number(text, self.PATTERNS['refinance_fee'])
        fees.refinance_fee = self._parse_fee_percentage(refi_fee)

        # Financing/origination fee
        fin_fee = self._extract_number(text, self.PATTERNS['financing_fee'])
        fees.financing_fee = self._parse_fee_percentage(fin_fee)

        # Look for promote/waterfall tiers - extract structured promote % and hurdle %
        # Collect all candidate (promote_pct, hurdle_pct, label) tuples across all patterns,
        # then de-duplicate and sort by hurdle ascending (Tier 1 = lower hurdle)
        promote_candidates = []
        promote_patterns = [
            # "80/20 split above X%" or "Profit Split: 80/20 (LP/GP) above X%"
            # GP gets the smaller of the two numbers; indices: 1=LP, 2=GP, 3=hurdle
            (r'(?:profit\s*split[:\s]*)?(\d+)\s*/\s*(\d+)\s*(?:\(lp/gp\))?\s*(?:split|waterfall)?\s*(?:above|after)\s*(?:a\s+)?(\d+(?:\.\d+)?)\s*%',
             2, 3),
            # "20% promote/carry above X% IRR/return"
            (r'(\d+)\s*%\s*(?:promote|carried\s*interest|carry|gp\s*promote)\s*(?:above|after|over|on)\s+(?:a\s+)?(\d+(?:\.\d+)?)\s*%\s*(?:irr|return|hurdle|pref)?',
             1, 2),
            # "promote/carry of 20% above X%"
            (r'(?:promote|carried\s*interest|carry)[:\s]+(?:of\s+)?(\d+)\s*%\s*(?:above|after|over)\s+(\d+(?:\.\d+)?)\s*%',
             1, 2),
            # "GP receives 20% of profits above X% IRR"
            (r'gp\s+receives?\s+(\d+)\s*%\s+(?:of\s+)?(?:profits?|proceeds?|upside)\s+(?:above|after|over)\s+(?:a\s+)?(\d+(?:\.\d+)?)\s*%',
             1, 2),
            # "20% carried interest once investors receive X%"
            (r'(\d+)\s*%\s*(?:carried\s*interest|promote)\s+(?:above|after|once)[^.]*?(\d+(?:\.\d+)?)\s*%',
             1, 2),
            # "Sponsor/Manager receives 20% of distributable cash/profits after hurdle"
            (r'(?:sponsor|manager|gp)\s+(?:shall\s+)?receive[s]?\s+(\d+)\s*%\s+(?:of\s+)?(?:distributable|excess|remaining)',
             1, None),
            # "Carried Interest: 20%" or "Promote: 20%" (standalone, no hurdle in sentence)
            (r'(?:carried\s*interest|promote|performance\s*(?:fee|allocation))[:\s]+(\d+)\s*%',
             1, None),
            # "20% carried interest" or "20% promote" standalone
            (r'(\d+)\s*%\s+(?:carried\s*interest|promote|performance\s*fee)',
             1, None),
        ]
        seen = set()
        for pattern_tuple in promote_patterns:
            pattern = pattern_tuple[0]
            promote_idx = pattern_tuple[1]
            hurdle_idx = pattern_tuple[2] if len(pattern_tuple) > 2 else None
            for match in re.finditer(pattern, text, re.IGNORECASE):
                promote_pct = self._safe_float(match.group(promote_idx))
                hurdle_pct = None
                if hurdle_idx is not None and hurdle_idx <= match.lastindex:
                    hurdle_pct = self._safe_float(match.group(hurdle_idx))
                if promote_pct and 5 <= promote_pct <= 50:
                    hurdle_val = (hurdle_pct / 100) if hurdle_pct and hurdle_pct < 50 else None
                    key = (round(promote_pct), round(hurdle_pct) if hurdle_pct else None)
                    if key not in seen:
                        seen.add(key)
                        promote_candidates.append((promote_pct / 100, hurdle_val, match.group(0).strip()))

        # If we found promote but no hurdle, try to link with preferred return
        if promote_candidates and promote_candidates[0][1] is None:
            # Use preferred return as the hurdle if available
            pref_return = terms.preferred_return if 'terms' in dir() else None
            if pref_return is None:
                # Try to extract from text
                pref_match = re.search(r'(?:preferred\s*return|pref|irr\s*hurdle)[:\s]+(\d+(?:\.\d+)?)\s*%', text, re.IGNORECASE)
                if pref_match:
                    pref_return = self._safe_float(pref_match.group(1))
                    if pref_return:
                        pref_return = pref_return / 100 if pref_return > 1 else pref_return
            if pref_return and 0.04 <= pref_return <= 0.15:
                # Update candidates with the preferred return as hurdle
                promote_candidates = [(p, pref_return if h is None else h, l) for p, h, l in promote_candidates]

        # Sort by hurdle ascending (Tier 1 = lower hurdle, then higher)
        promote_candidates.sort(key=lambda x: x[1] if x[1] is not None else 0)
        promote_candidates.sort(key=lambda x: x[1] if x[1] is not None else 0)

        if promote_candidates:
            fees.promote_tier_1_pct = promote_candidates[0][0]
            fees.promote_tier_1_hurdle = promote_candidates[0][1]
            fees.promote_tier_1_label = promote_candidates[0][2]
        if len(promote_candidates) > 1:
            fees.promote_tier_2_pct = promote_candidates[1][0]
            fees.promote_tier_2_hurdle = promote_candidates[1][1]
            fees.promote_tier_2_label = promote_candidates[1][2]

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

    def _extract_market_data(self, text: str, text_lower: str) -> MarketData:
        """Extract market data from the OM (typically from market comparison sections)"""
        market = MarketData()

        # Extract vacancy rate from market tables
        vacancy_patterns = [
            r'(?:market\s+)?vacancy\s*(?:rate)?[:\s]*([\d.]+)\s*%',
            r'vacancy[:\s]*([\d.]+)\s*%',
            r'([\d.]+)\s*%\s*vacancy',
        ]
        for pattern in vacancy_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                vacancy = self._safe_float(match.group(1))
                if vacancy is not None:
                    vacancy_val = vacancy if vacancy <= 1 else vacancy / 100
                    if 0 <= vacancy_val <= 0.30:  # Sanity check - up to 30% vacancy
                        market.market_vacancy_rate = vacancy_val
                        break

        # Extract market rent PSF
        market_rent_patterns = [
            r'(?:market|asking)\s*rent\s*(?:psf)?[:\s]*\$?([\d.]+)',
            r'psf\s*(?:market\s*)?rent[:\s]*\$?([\d.]+)',
        ]
        for pattern in market_rent_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                rent = self._safe_float(match.group(1))
                if rent and 1 < rent < 100:  # PSF rent sanity check
                    market.market_rent_psf = rent
                    break

        # Extract market cap rate
        market_cap_patterns = [
            r'(?:market|comparable)\s*cap\s*(?:rate)?[:\s]*([\d.]+)\s*%',
            r'market\s+(?:cap\s+)?rate[:\s]*([\d.]+)\s*%',
        ]
        for pattern in market_cap_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                cap = self._safe_float(match.group(1))
                if cap is not None:
                    cap_val = cap if cap <= 1 else cap / 100
                    if 0.02 <= cap_val <= 0.15:
                        market.market_cap_rate = cap_val
                        break

        # Extract rent growth
        rent_growth_patterns = [
            r'rent\s*growth[:\s]*([\d.]+)\s*%',
            r'([\d.]+)\s*%\s*rent\s*growth',
        ]
        for pattern in rent_growth_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                growth = self._safe_float(match.group(1))
                if growth is not None:
                    growth_val = growth if growth <= 1 else growth / 100
                    if -0.1 <= growth_val <= 0.2:  # -10% to +20%
                        market.rent_growth_1yr = growth_val
                        break

        # Extract absorption rate
        absorption_patterns = [
            r'absorption\s*(?:rate)?[:\s]*([\d.]+)\s*%',
            r'([\d.]+)\s*%\s*absorption',
        ]
        for pattern in absorption_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                absorption = self._safe_float(match.group(1))
                if absorption is not None:
                    absorption_val = absorption if absorption <= 1 else absorption / 100
                    if 0 <= absorption_val <= 1:
                        market.absorption_rate = absorption_val
                        break

        return market

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
