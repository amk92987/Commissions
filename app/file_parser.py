import pandas as pd
import os
from lxml import etree


def parse_file(filepath):
    """
    Parse uploaded file (CSV, XLS, XLSX, or XML) and return a pandas DataFrame.
    """
    _, ext = os.path.splitext(filepath)
    ext = ext.lower()

    if ext == '.csv':
        return parse_csv(filepath)
    elif ext == '.xlsx':
        return parse_xlsx(filepath)
    elif ext == '.xls':
        return parse_xls(filepath)
    elif ext == '.xml':
        return parse_xml(filepath)
    else:
        raise ValueError(f"Unsupported file format: {ext}")


def parse_csv(filepath):
    """Parse CSV file."""
    # Try different encodings
    encodings = ['utf-8', 'latin-1', 'cp1252']
    for encoding in encodings:
        try:
            df = pd.read_csv(filepath, encoding=encoding)
            return df
        except UnicodeDecodeError:
            continue
    raise ValueError("Could not decode CSV file with any supported encoding")


def parse_xlsx(filepath):
    """Parse XLSX (Excel 2007+) file."""
    return pd.read_excel(filepath, engine='openpyxl')


def parse_xls(filepath):
    """Parse XLS (Excel 97-2003) file."""
    return pd.read_excel(filepath, engine='xlrd')


def parse_xml(filepath):
    """
    Parse XML file - specifically designed for Aflac format.
    Will need to be customized based on actual Aflac XML structure.
    """
    tree = etree.parse(filepath)
    root = tree.getroot()

    # Try to auto-detect structure
    records = []

    # Look for repeating elements (likely data rows)
    # This is a generic approach - will be refined when we see actual Aflac XML
    for child in root:
        record = {}
        for element in child:
            # Handle nested elements
            if len(element) > 0:
                for sub in element:
                    key = f"{element.tag}_{sub.tag}"
                    record[key] = sub.text
            else:
                record[element.tag] = element.text
        if record:
            records.append(record)

    if records:
        return pd.DataFrame(records)

    # Fallback: try to read as flat structure
    record = {}
    for element in root.iter():
        if element.text and element.text.strip():
            record[element.tag] = element.text.strip()

    if record:
        return pd.DataFrame([record])

    raise ValueError("Could not parse XML structure")


def get_file_columns(filepath):
    """Get column names from a file without loading all data."""
    df = parse_file(filepath)
    return list(df.columns)


def get_file_preview(filepath, rows=5):
    """Get a preview of the file data."""
    df = parse_file(filepath)
    return df.head(rows).to_dict('records'), list(df.columns)
