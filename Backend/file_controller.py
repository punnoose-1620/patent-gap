def xml_to_text(xml_content):
    """
    Converts XML content to plain text with error handling.
    
    Args:
        xml_content (str or bytes): The XML content
        
    Returns:
        str: The text content from the XML, or empty string if parsing fails
    """
    import xml.etree.ElementTree as ET
    if xml_content is None:
        return ""
    
    try:
        # Handle bytes input
        if isinstance(xml_content, bytes):
            xml_content = xml_content.decode('utf-8', errors='ignore')
        
        # Parse XML
        root = ET.fromstring(xml_content)
        
        # Extract all text recursively (handles nested elements)
        return ' '.join(root.itertext()).strip()
        
    except ET.ParseError as e:
        print(f"XML ParseError: {e}")
    except UnicodeDecodeError as e:
        print(f"Unicode decode error: {e}")
    except Exception as e:
        print(f"Error converting XML to text: {e}")
    return ""

def readFromXmlUrl(xml_url, headers=None, params=None):
    """
    Downloads XML content from the provided URL and returns it as a string.

    Args:
        xml_url (str): The URL of the XML file

    Returns:
        str: The raw XML content as text, or None if download failed
    """
    import requests

    try:
        response = requests.get(xml_url, headers=headers, params=params)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error fetching XML from {xml_url}: {e}")
        return ""

def readFromPdfUrl(pdf_url, headers=None, params=None):
    """
    Downloads a PDF file from the provided URL and returns its text content as a string.

    Args:
        pdf_url (str): The URL of the PDF file

    Returns:
        str: The extracted text content from the PDF, or None if reading failed
    """
    import requests
    import io
    import PyPDF2

    try:
        response = requests.get(pdf_url, headers=headers, params=params)
        response.raise_for_status()
        pdf_bytes = io.BytesIO(response.content)
        reader = PyPDF2.PdfReader(pdf_bytes)
        text = ""
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted
        return text
    except Exception as e:
        print(f"Error reading PDF from {pdf_url}: {e}")
        return None

def readDocumentFromUrl(url:str, headers:dict=None, params:dict=None) -> str:
    """
    Reads a document from the provided URL and returns its text content as a string.
    Args:
        url (str): The URL of the document
    Returns:
        str: The extracted text content from the document, or None if reading failed
    """
    if url.endswith('.xml'):
        xml_content = readFromXmlUrl(url, headers=headers, params=params)
        text_content = xml_to_text(xml_content)
        return text_content
    elif url.endswith('.pdf'):
        return readFromPdfUrl(url, headers=headers, params=params)