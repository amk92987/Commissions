"""
Carrier configuration system.
Each carrier has specific transformation rules, lookups, and file type mappings.
"""
import json
import os
from typing import Dict, List, Optional
import pandas as pd


class CarrierConfig:
    """Manages carrier-specific configurations including lookups and transformation rules."""

    def __init__(self, data_folder: str):
        self.data_folder = data_folder
        self.configs_file = os.path.join(data_folder, 'carrier_configs.json')
        self.configs = self._load_configs()

    def _load_configs(self) -> Dict:
        """Load carrier configs from file."""
        if os.path.exists(self.configs_file):
            with open(self.configs_file, 'r') as f:
                return json.load(f)
        # Initialize with Manhattan Life config
        return self._get_default_configs()

    def _get_default_configs(self) -> Dict:
        """Get default carrier configurations."""
        return {
            "Manhattan Life": {
                "file_types": {
                    "commission": {
                        "template": "Policy And Transactions Template (13).csv",
                        "identifier_columns": ["Record Type", "Group No.", "Policy", "Owner Name"],
                        "description": "Commission statement file"
                    },
                    "chargeback": {
                        "template": "Commission Chargebacks Template (10).csv",
                        "identifier_columns": ["Policy Owner Name", "Policy Number", "# of Days Lapsed"],
                        "description": "Chargeback/lapse report"
                    }
                },
                "lookups": {
                    "plan_to_product_type": {
                        "DVH SELECT $5,000 POL MAX WITH $100 DEDUCT": "Dental with Vision",
                        "DVH SELECT $5,000 POL MAX WITH $0 DEDUCT": "Dental with Vision",
                        "DVH SELECT $3,000 POL MAX WITH $0 DEDUCT": "Dental with Vision",
                        "DVH SELECT $3,000 POL MAX WITH $100 DEDUCT": "Dental with Vision",
                        "DVH SELECT $1,500 POL MAX WITH $0 DEDUCT": "Dental with Vision",
                        "DVH SELECT $1,500 POL MAX WITH $100 DEDUCT": "Dental with Vision",
                        "DVH SELECT $1,000 POL MAX WITH $0 DEDUCT": "Dental with Vision",
                        "DVH SELECT $1,000 POL MAX WITH $100 DEDUCT": "Dental with Vision",
                        "DVH REFRESH, GENERIC PLAN, $1,000 PY MAX": "Dental with Vision",
                        "DVH REFRESH, GENERIC PLAN, $1,500 PY MAX": "Dental with Vision",
                        "DVH REFRESH, GENERIC PLAN, $3,000 PY MAX": "Dental with Vision",
                        "DVH REFRESH, GENERIC PLAN, $5,000 PY MAX": "Dental with Vision",
                        "DENTAL/VISION/HEARING  $1500 POL MAX": "Dental with Vision",
                        "PAID ENHANCED - 24 HR ACC POLICY 2 UNITS": "Accident",
                        "PAID ENHANCED - 24 HR ACC POLICY 2 UNIT": "Accident",
                        "PAID ENHANCED - 24 HR ACC POLICY 1 UNIT": "Accident",
                        "PAID ENHANCED - NON-OCC ACCIDENT 2 UNITS": "Accident",
                        "MIAC 24 HR ACCIDENT EXPENSE FL": "Accident",
                        "2013 OFF THE JOB ACCIDENT EXPENSE": "Accident",
                        "AFFORDABLE CHOICE ENHANCED ELITE PLUS": "Fixed Indemnity",
                        "AFFORDABLE CHOICE ENHANCED ELITE": "Fixed Indemnity",
                        "AFFORDABLE CHOICE ENHANCED CLASSIC PLUS": "Fixed Indemnity",
                        "AFFORDABLE CHOICE ENHANCED CLASSIC": "Fixed Indemnity",
                        "HOSPITAL INDEMNITY SELECT": "Hospital Indemnity",
                        "LUMP SUM CANCER": "Critical Illness",
                        "LUMP SUM HEART ATTACK AND STROKE": "Critical Illness",
                        "CRITICAL PROTECTION & RECOVERY W/ CANCER (B)": "Critical Illness"
                    },
                    "plan_to_plan_name": {
                        "DVH SELECT $5,000 POL MAX WITH $100 DEDUCT": "Dental, Vision, Hearing & Dental, Vision, Hearing Select ",
                        "DVH SELECT $5,000 POL MAX WITH $0 DEDUCT": "Dental, Vision, Hearing & Dental, Vision, Hearing Select ",
                        "DVH SELECT $3,000 POL MAX WITH $0 DEDUCT": "Dental, Vision, Hearing & Dental, Vision, Hearing Select ",
                        "DVH SELECT $3,000 POL MAX WITH $100 DEDUCT": "Dental, Vision, Hearing & Dental, Vision, Hearing Select ",
                        "DVH SELECT $1,500 POL MAX WITH $0 DEDUCT": "Dental, Vision, Hearing & Dental, Vision, Hearing Select ",
                        "DVH SELECT $1,500 POL MAX WITH $100 DEDUCT": "Dental, Vision, Hearing & Dental, Vision, Hearing Select ",
                        "DVH SELECT $1,000 POL MAX WITH $0 DEDUCT": "Dental, Vision, Hearing & Dental, Vision, Hearing Select ",
                        "DVH SELECT $1,000 POL MAX WITH $100 DEDUCT": "Dental, Vision, Hearing & Dental, Vision, Hearing Select ",
                        "DVH REFRESH, GENERIC PLAN, $1,000 PY MAX": "Dental, Vision, Hearing & Dental, Vision, Hearing Select ",
                        "DVH REFRESH, GENERIC PLAN, $1,500 PY MAX": "Dental, Vision, Hearing & Dental, Vision, Hearing Select ",
                        "DVH REFRESH, GENERIC PLAN, $3,000 PY MAX": "Dental, Vision, Hearing & Dental, Vision, Hearing Select ",
                        "DVH REFRESH, GENERIC PLAN, $5,000 PY MAX": "Dental, Vision, Hearing & Dental, Vision, Hearing Select ",
                        "DENTAL/VISION/HEARING  $1500 POL MAX": "Dental, Vision, Hearing & Dental, Vision, Hearing Select ",
                        "PAID ENHANCED - 24 HR ACC POLICY 2 UNITS": "PAID Personal Accident & DI Rider, and Accident Express ",
                        "PAID ENHANCED - 24 HR ACC POLICY 2 UNIT": "PAID Personal Accident & DI Rider, and Accident Express ",
                        "PAID ENHANCED - 24 HR ACC POLICY 1 UNIT": "PAID Personal Accident & DI Rider, and Accident Express ",
                        "PAID ENHANCED - NON-OCC ACCIDENT 2 UNITS": "PAID Personal Accident & DI Rider, and Accident Express ",
                        "MIAC 24 HR ACCIDENT EXPENSE FL": "PAID Personal Accident & DI Rider, and Accident Express",
                        "2013 OFF THE JOB ACCIDENT EXPENSE": "PAID Personal Accident & DI Rider, and Accident Express",
                        "AFFORDABLE CHOICE ENHANCED ELITE PLUS": "Affordable Choice",
                        "AFFORDABLE CHOICE ENHANCED ELITE": "Affordable Choice",
                        "AFFORDABLE CHOICE ENHANCED CLASSIC PLUS": "Affordable Choice",
                        "AFFORDABLE CHOICE ENHANCED CLASSIC": "Affordable Choice",
                        "HOSPITAL INDEMNITY SELECT": "Hospital Indemnity Select 18-64.5",
                        "LUMP SUM CANCER": "Cancer, Heart Attack, Stroke",
                        "LUMP SUM HEART ATTACK AND STROKE": "Cancer, Heart Attack, Stroke",
                        "CRITICAL PROTECTION & RECOVERY W/ CANCER (B)": "Critical Protection CPR-Critical Illness"
                    }
                },
                "rules": []
            }
        }

    def _save_configs(self):
        """Save carrier configs to file."""
        with open(self.configs_file, 'w') as f:
            json.dump(self.configs, f, indent=2)

    def get_carrier_config(self, carrier_name: str) -> Optional[Dict]:
        """Get configuration for a specific carrier."""
        return self.configs.get(carrier_name)

    def get_all_carriers(self) -> List[str]:
        """Get list of all configured carriers."""
        return list(self.configs.keys())

    def detect_file_type(self, carrier_name: str, columns: List[str]) -> Optional[str]:
        """Detect the file type based on columns."""
        config = self.get_carrier_config(carrier_name)
        if not config:
            return None

        for file_type, file_config in config.get('file_types', {}).items():
            identifier_cols = file_config.get('identifier_columns', [])
            # Check if most identifier columns are present
            matches = sum(1 for col in identifier_cols if col in columns)
            if matches >= len(identifier_cols) * 0.5:  # At least 50% match
                return file_type

        return None

    def get_lookup(self, carrier_name: str, lookup_name: str, key: str) -> Optional[str]:
        """Get a value from a carrier's lookup table."""
        config = self.get_carrier_config(carrier_name)
        if not config:
            return None

        lookups = config.get('lookups', {})
        lookup_table = lookups.get(lookup_name, {})
        return lookup_table.get(key)

    def update_lookup(self, carrier_name: str, lookup_name: str, key: str, value: str):
        """Update or add a lookup entry."""
        if carrier_name not in self.configs:
            self.configs[carrier_name] = {"lookups": {}, "file_types": {}, "rules": []}

        if 'lookups' not in self.configs[carrier_name]:
            self.configs[carrier_name]['lookups'] = {}

        if lookup_name not in self.configs[carrier_name]['lookups']:
            self.configs[carrier_name]['lookups'][lookup_name] = {}

        self.configs[carrier_name]['lookups'][lookup_name][key] = value
        self._save_configs()

    def delete_lookup_entry(self, carrier_name: str, lookup_name: str, key: str):
        """Delete a lookup entry."""
        if carrier_name in self.configs:
            lookups = self.configs[carrier_name].get('lookups', {})
            if lookup_name in lookups and key in lookups[lookup_name]:
                del lookups[lookup_name][key]
                self._save_configs()

    def get_all_lookups(self, carrier_name: str) -> Dict:
        """Get all lookups for a carrier."""
        config = self.get_carrier_config(carrier_name)
        if not config:
            return {}
        return config.get('lookups', {})

    def initialize_default_configs(self):
        """Initialize default configs if not exists."""
        if not os.path.exists(self.configs_file):
            self.configs = self._get_default_configs()
            self._save_configs()
