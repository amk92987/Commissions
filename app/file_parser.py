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
    """Parse CSV file, handling multi-row headers like Manhattan Life."""
    encodings = ['utf-8', 'latin-1', 'cp1252']

    for encoding in encodings:
        try:
            # First, try to detect if this is a multi-row header file
            # Read first few rows to check
            test_df = pd.read_csv(filepath, encoding=encoding, nrows=5, header=None)

            # Check if first row looks like partial headers (has empty-ish values like " ")
            first_row = test_df.iloc[0].astype(str).tolist()
            second_row = test_df.iloc[1].astype(str).tolist() if len(test_df) > 1 else []

            # Manhattan Life style: first row has some headers, second row has more
            # Detect by checking if both rows have string values and first row has " " entries
            is_multi_header = False
            if second_row:
                first_row_blanks = sum(1 for v in first_row if v.strip() in ['', ' '])
                # If first row has blank-ish columns and second row looks like headers
                if first_row_blanks >= 3:
                    # Check if second row values look like column names (not data)
                    second_row_looks_like_headers = all(
                        not str(v).replace('.', '').replace('-', '').replace('/', '').isdigit()
                        for v in second_row[:10] if str(v).strip()
                    )
                    if second_row_looks_like_headers:
                        is_multi_header = True

            if is_multi_header:
                # Combine first two rows into single header
                # Use second row as base, fill blanks from first row
                combined_header = []
                for i, (h1, h2) in enumerate(zip(first_row, second_row)):
                    h1 = str(h1).strip()
                    h2 = str(h2).strip()
                    if h2 and h2 != ' ':
                        combined_header.append(h2)
                    elif h1 and h1 != ' ':
                        combined_header.append(h1)
                    else:
                        combined_header.append(f'Column_{i}')

                # Read full file, skip first 2 rows, use our combined header
                df = pd.read_csv(filepath, encoding=encoding, skiprows=2, header=None)
                # Ensure we have enough column names
                while len(combined_header) < len(df.columns):
                    combined_header.append(f'Column_{len(combined_header)}')
                df.columns = combined_header[:len(df.columns)]
                return df
            else:
                # Normal single-row header
                df = pd.read_csv(filepath, encoding=encoding)
                return df

        except UnicodeDecodeError:
            continue
        except Exception as e:
            # If multi-header detection fails, try normal read
            try:
                df = pd.read_csv(filepath, encoding=encoding)
                return df
            except:
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
    # Convert to JSON-safe format (handle NaN, dates, etc.)
    preview_df = df.head(rows).copy()

    # Handle duplicate column names by making them unique
    cols = list(preview_df.columns)
    seen = {}
    new_cols = []
    for col in cols:
        if col in seen:
            seen[col] += 1
            new_cols.append(f"{col}_{seen[col]}")
        else:
            seen[col] = 0
            new_cols.append(col)
    preview_df.columns = new_cols

    # Replace NaN with None for JSON serialization
    preview_df = preview_df.where(pd.notnull(preview_df), None)
    # Convert any remaining problematic values to strings
    for col in preview_df.columns:
        preview_df[col] = preview_df[col].apply(lambda x: str(x) if x is not None else '')
    return preview_df.to_dict('records'), new_cols
