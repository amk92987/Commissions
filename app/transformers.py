"""
Carrier-specific data transformers.
Each carrier has its own transformation logic to convert source data to template format.
"""
import pandas as pd
from typing import Dict, Optional
from datetime import datetime
from app.carrier_configs import CarrierConfig


class BaseTransformer:
    """Base class for carrier transformers."""

    def __init__(self, carrier_config: CarrierConfig, carrier_name: str):
        self.carrier_config = carrier_config
        self.carrier_name = carrier_name

    def transform(self, df: pd.DataFrame, file_type: str) -> pd.DataFrame:
        """Transform source data to template format."""
        raise NotImplementedError


class ManhattanLifeTransformer(BaseTransformer):
    """Transformer for Manhattan Life files."""

    def transform(self, df: pd.DataFrame, file_type: str) -> pd.DataFrame:
        if file_type == 'commission':
            return self._transform_commission(df)
        elif file_type == 'chargeback':
            return self._transform_chargeback(df)
        else:
            raise ValueError(f"Unknown file type: {file_type}")

    def _transform_commission(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transform commission file to Policy And Transactions template."""
        # Normalize column names (remove extra spaces, handle variations)
        df.columns = df.columns.str.strip()

        # Find the right column names (they may vary slightly)
        col_map = self._find_columns(df, {
            'group_no': ['Group No.', 'Bill Ctrl/', 'Group No'],
            'owner_name': ['Owner Name', 'Owner'],
            'payment_date': ['Payment Date', 'Payment'],
            'ptd': ['Paid To Date', 'PTD', 'Paid To'],
            'issue_date': ['Issue Date', 'Issue'],
            'premium': ['Premium'],
            'commission': ['Commission'],
            'advance_repay': ['Advance Repay', 'Advance'],
            'issue_state': ['Issue State', 'Issue'],
            'plan_description': ['Plan Description', 'Plan Desc'],
            'writing_agent': ['Writing Agent'],
        })

        output = pd.DataFrame()

        # PolicyNo - from Group No.
        output['PolicyNo'] = df[col_map['group_no']]

        # PHFirst - empty
        output['PHFirst'] = ''

        # PHLast - from Owner Name
        output['PHLast'] = df[col_map['owner_name']]

        # Status - hardcoded
        output['Status'] = 'Active'

        # Issuer - hardcoded
        output['Issuer'] = 'Manhattan Life'

        # State - from Issue State
        output['State'] = df[col_map['issue_state']]

        # ProductType - lookup from Plan Description
        output['ProductType'] = df[col_map['plan_description']].apply(
            lambda x: self.carrier_config.get_lookup(
                self.carrier_name, 'plan_to_product_type', str(x).strip()
            ) or ''
        )

        # PlanName - lookup from Plan Description
        output['PlanName'] = df[col_map['plan_description']].apply(
            lambda x: self.carrier_config.get_lookup(
                self.carrier_name, 'plan_to_plan_name', str(x).strip()
            ) or ''
        )

        # SubmittedDate - from Issue Date
        output['SubmittedDate'] = self._format_date(df[col_map['issue_date']])

        # EffectiveDate - from Issue Date
        output['EffectiveDate'] = self._format_date(df[col_map['issue_date']])

        # TermDate - empty
        output['TermDate'] = ''

        # PaySched - hardcoded
        output['PaySched'] = 'Monthly'

        # PayCode - hardcoded
        output['PayCode'] = 'Default'

        # WritingAgentID - from Writing Agent
        output['WritingAgentID'] = df[col_map['writing_agent']]

        # Premium
        output['Premium'] = df[col_map['premium']]

        # CommPrem - same as Premium
        output['CommPrem'] = df[col_map['premium']]

        # TranDate - from Payment Date
        output['TranDate'] = self._format_date(df[col_map['payment_date']])

        # CommReceived - IF(Commission <> 0, Commission, Advance Repay)
        commission = pd.to_numeric(df[col_map['commission']], errors='coerce').fillna(0)
        advance_repay = pd.to_numeric(df[col_map['advance_repay']], errors='coerce').fillna(0)
        output['CommReceived'] = commission.where(commission != 0, advance_repay)

        # PTD - from PTD column
        output['PTD'] = self._format_date(df[col_map['ptd']])

        # NoPayMon - hardcoded
        output['NoPayMon'] = 1

        # MemberCount - empty
        output['MemberCount'] = ''

        # Note - Plan Description
        output['Note'] = df[col_map['plan_description']]

        return output

    def _transform_chargeback(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transform chargeback file to Commission Chargebacks template."""
        df.columns = df.columns.str.strip()

        col_map = self._find_columns(df, {
            'policy_number': ['Policy Number', 'Policy No', 'PolicyNo'],
            'paid_to_date': ['Paid To Date', 'PTD'],
        })

        output = pd.DataFrame()

        # PolicyNo
        output['PolicyNo'] = df[col_map['policy_number']]

        # Issuer - hardcoded
        output['Issuer'] = 'Manhattan Life'

        # CancelDate - from Paid To Date
        output['CancelDate'] = self._format_date(df[col_map['paid_to_date']])

        # ProcessDate - from Paid To Date
        output['ProcessDate'] = self._format_date(df[col_map['paid_to_date']])

        # PolicyStatus - hardcoded
        output['PolicyStatus'] = 'Chargeback'

        # Note - empty
        output['Note'] = ''

        return output

    def _find_columns(self, df: pd.DataFrame, column_map: Dict) -> Dict:
        """Find actual column names from possible variations."""
        result = {}
        df_cols = [c.strip() for c in df.columns]

        for key, possibilities in column_map.items():
            found = None
            for poss in possibilities:
                # Exact match
                if poss in df_cols:
                    found = poss
                    break
                # Partial match
                for col in df_cols:
                    if poss.lower() in col.lower():
                        found = col
                        break
                if found:
                    break

            if not found:
                # Use first possibility as default (may cause error if not found)
                found = possibilities[0]

            result[key] = found

        return result

    def _format_date(self, series: pd.Series) -> pd.Series:
        """Format dates to M/D/YYYY format."""
        def format_single(val):
            if pd.isna(val) or val == '' or val == ' ':
                return ''
            try:
                if isinstance(val, datetime):
                    return val.strftime('%-m/%-d/%Y') if hasattr(val, 'strftime') else val.strftime('%m/%d/%Y').lstrip('0').replace('/0', '/')
                # Try parsing string
                dt = pd.to_datetime(val)
                # Format without leading zeros
                return f"{dt.month}/{dt.day}/{dt.year}"
            except:
                return str(val)

        return series.apply(format_single)


def get_transformer(carrier_name: str, carrier_config: CarrierConfig) -> Optional[BaseTransformer]:
    """Get the appropriate transformer for a carrier."""
    transformers = {
        'Manhattan Life': ManhattanLifeTransformer,
    }

    transformer_class = transformers.get(carrier_name)
    if transformer_class:
        return transformer_class(carrier_config, carrier_name)
    return None
