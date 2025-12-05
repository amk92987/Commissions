import json
import os
from typing import Optional, Dict, List


class CarrierRecognition:
    """
    Recognizes carriers based on file characteristics and historical data.
    Stores carrier signatures (column patterns) for future recognition.
    """

    def __init__(self, data_folder: str):
        self.data_folder = data_folder
        self.signatures_file = os.path.join(data_folder, 'carrier_signatures.json')
        self.signatures = self._load_signatures()

    def _load_signatures(self) -> Dict:
        """Load carrier signatures from file."""
        if os.path.exists(self.signatures_file):
            with open(self.signatures_file, 'r') as f:
                return json.load(f)
        return {}

    def _save_signatures(self):
        """Save carrier signatures to file."""
        with open(self.signatures_file, 'w') as f:
            json.dump(self.signatures, f, indent=2)

    def recognize_carrier(self, columns: List[str], filename: str) -> Optional[str]:
        """
        Try to recognize carrier based on column signature and filename.
        Returns carrier name if recognized, None otherwise.
        """
        # Create a signature from columns
        col_signature = self._create_signature(columns)

        # Check for exact signature match
        for carrier, data in self.signatures.items():
            if data.get('column_signature') == col_signature:
                return carrier

        # Check for filename pattern match
        filename_lower = filename.lower()
        for carrier, data in self.signatures.items():
            patterns = data.get('filename_patterns', [])
            for pattern in patterns:
                if pattern.lower() in filename_lower:
                    return carrier

        # Check for partial column match (at least 80% match)
        for carrier, data in self.signatures.items():
            stored_cols = set(data.get('columns', []))
            current_cols = set(columns)
            if stored_cols and current_cols:
                overlap = len(stored_cols & current_cols)
                max_len = max(len(stored_cols), len(current_cols))
                if overlap / max_len >= 0.8:
                    return carrier

        return None

    def _create_signature(self, columns: List[str]) -> str:
        """Create a unique signature from column names."""
        # Normalize and sort column names
        normalized = sorted([col.lower().strip() for col in columns])
        return '|'.join(normalized)

    def register_carrier(self, carrier_name: str, columns: List[str], filename: str):
        """
        Register a new carrier or update existing carrier signature.
        """
        col_signature = self._create_signature(columns)

        if carrier_name not in self.signatures:
            self.signatures[carrier_name] = {
                'column_signature': col_signature,
                'columns': columns,
                'filename_patterns': [],
                'file_count': 0
            }

        # Update signature
        self.signatures[carrier_name]['column_signature'] = col_signature
        self.signatures[carrier_name]['columns'] = columns
        self.signatures[carrier_name]['file_count'] += 1

        # Extract potential filename pattern
        # Remove common extensions and date patterns
        import re
        pattern = re.sub(r'\d{4}[-_]\d{2}[-_]\d{2}', '', filename)
        pattern = re.sub(r'\d{2}[-_]\d{2}[-_]\d{4}', '', pattern)
        pattern = re.sub(r'\.(csv|xlsx?|xml)$', '', pattern, flags=re.IGNORECASE)
        pattern = pattern.strip('_- ')

        if pattern and pattern not in self.signatures[carrier_name]['filename_patterns']:
            self.signatures[carrier_name]['filename_patterns'].append(pattern)

        self._save_signatures()

    def get_all_carriers(self) -> List[str]:
        """Get list of all registered carriers."""
        return list(self.signatures.keys())

    def get_carrier_info(self, carrier_name: str) -> Optional[Dict]:
        """Get information about a specific carrier."""
        return self.signatures.get(carrier_name)
