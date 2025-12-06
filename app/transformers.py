"""
Carrier-specific data transformers.
Each carrier has its own transformation logic to convert source data to template format.
"""
import pandas as pd
from typing import Dict, Optional, List, Tuple
from datetime import datetime
from app.carrier_configs import CarrierConfig
import os


class BaseTransformer:
    """Base class for carrier transformers."""

    def __init__(self, carrier_config: CarrierConfig, carrier_name: str):
        self.carrier_config = carrier_config
        self.carrier_name = carrier_name
        self.agent_lookup = None  # Will be loaded when needed

    def transform(self, df: pd.DataFrame, file_type: str) -> pd.DataFrame:
        """Transform source data to template format."""
        raise NotImplementedError

    def get_available_outputs(self, df: pd.DataFrame) -> List[str]:
        """Return list of output types available in this file."""
        return ['commission']

    def transform_all(self, df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """Transform to all available output types. Returns dict of {type: dataframe}."""
        results = {}
        for output_type in self.get_available_outputs(df):
            try:
                results[output_type] = self.transform(df, output_type)
            except Exception as e:
                print(f"Error transforming {output_type}: {e}")
        return results


class ManhattanLifeTransformer(BaseTransformer):
    """Transformer for Manhattan Life files."""

    def transform(self, df: pd.DataFrame, file_type: str) -> pd.DataFrame:
        if file_type == 'commission':
            return self._transform_commission(df)
        elif file_type == 'chargeback':
            return self._transform_chargeback(df)
        elif file_type == 'adjustment':
            return self._transform_adjustment(df)
        else:
            raise ValueError(f"Unknown file type: {file_type}")

    def get_available_outputs(self, df: pd.DataFrame) -> List[str]:
        """Check what output types are available based on data content."""
        available = []
        df.columns = df.columns.str.strip()
        col_list = [c.strip() for c in df.columns]

        # Check if this is a chargeback file (has Policy Number + Paid To Date, no exact "Policy" column)
        has_policy_number = 'Policy Number' in col_list
        has_paid_to_date = 'Paid To Date' in col_list
        has_exact_policy = 'Policy' in col_list  # Exact match only

        if has_policy_number and has_paid_to_date and not has_exact_policy:
            # This looks like a chargeback file
            available.append('chargeback')
            return available

        # Check for Policy column (returns index to handle duplicates)
        policy_col_idx = self._find_column(df, ['Policy'])

        if policy_col_idx is not None:
            # Get the column as a Series using iloc
            policy_series = df.iloc[:, policy_col_idx]

            # Check for APPT. FEE rows
            has_fees = policy_series.astype(str).str.strip().str.upper().eq('APPT. FEE').any()
            if has_fees:
                available.append('adjustment')

            # Check for regular commission rows (not APPT. FEE)
            has_commission = (~policy_series.astype(str).str.strip().str.upper().eq('APPT. FEE')).any()
            if has_commission:
                available.append('commission')
        else:
            # No policy column, assume commission
            available.append('commission')

        return available

    def _find_column(self, df: pd.DataFrame, possibilities: List[str]) -> Optional[int]:
        """Find a column by checking possible names. Returns column index to handle duplicates."""
        df_cols = [c.strip() for c in df.columns]
        for poss in possibilities:
            # Exact match first
            for idx, col in enumerate(df_cols):
                if col == poss:
                    return idx
            # Partial match
            for idx, col in enumerate(df_cols):
                if poss.lower() in col.lower():
                    return idx
        return None

    def _load_agent_lookup(self):
        """Load agent name to NPN lookup from Agent Appointment Summary."""
        if self.agent_lookup is not None:
            return

        self.agent_lookup = {}
        # Try to find the Agent Appointment Summary file
        possible_paths = [
            os.path.join(self.carrier_config.data_folder, 'Agent Appointment Summary.csv'),
            os.path.join(self.carrier_config.data_folder, '..', 'Samples', 'writing IDs and NPNs', 'Agent Appointment Summary.csv'),
        ]

        for path in possible_paths:
            if os.path.exists(path):
                try:
                    agent_df = pd.read_csv(path)
                    # Filter to Manhattan Life only
                    ml_agents = agent_df[agent_df['Issuer'].str.strip() == 'Manhattan Life']

                    for _, row in ml_agents.iterrows():
                        # Create name variations for lookup
                        first = str(row.get('First Name', '')).strip().upper()
                        last = str(row.get('Last Name', '')).strip().upper()
                        npn = str(row.get('NPN', '')).strip()
                        writing_id = str(row.get('Writing Agent ID', '')).strip()

                        if first and last and npn:
                            # Store with various key formats
                            # "FIRST LAST"
                            self.agent_lookup[f"{first} {last}"] = npn
                            # "LAST, FIRST" (as it appears in the commission file)
                            self.agent_lookup[f"{last}, {first}"] = npn
                            # Also store Writing Agent ID -> NPN
                            if writing_id:
                                self.agent_lookup[writing_id] = npn

                    print(f"Loaded {len(self.agent_lookup)} agent mappings for Manhattan Life")
                    break
                except Exception as e:
                    print(f"Error loading agent lookup: {e}")

        if not self.agent_lookup:
            print("Warning: Could not load Agent Appointment Summary")

    def _lookup_npn(self, agent_name) -> str:
        """Look up NPN for an agent name."""
        self._load_agent_lookup()

        if pd.isna(agent_name) or agent_name is None or str(agent_name).strip() == '' or not self.agent_lookup:
            return ''

        # Clean and uppercase the name
        clean_name = str(agent_name).strip().upper()

        # Direct lookup
        if clean_name in self.agent_lookup:
            return self.agent_lookup[clean_name]

        # Try various formats
        # If name is "LAST, FIRST MIDDLE" format, try "LAST, FIRST"
        if ',' in clean_name:
            parts = clean_name.split(',')
            if len(parts) >= 2:
                last = parts[0].strip()
                first_parts = parts[1].strip().split()
                if first_parts:
                    first = first_parts[0]
                    key = f"{last}, {first}"
                    if key in self.agent_lookup:
                        return self.agent_lookup[key]

        # Try "FIRST LAST" format
        parts = clean_name.replace(',', ' ').split()
        if len(parts) >= 2:
            # Try first last
            key = f"{parts[0]} {parts[-1]}"
            if key in self.agent_lookup:
                return self.agent_lookup[key]
            # Try last, first
            key = f"{parts[-1]}, {parts[0]}"
            if key in self.agent_lookup:
                return self.agent_lookup[key]

        return ''

    def _transform_commission(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transform commission file to Policy And Transactions template."""
        # Normalize column names (remove extra spaces, handle variations)
        df.columns = df.columns.str.strip()

        # Filter out APPT. FEE rows
        policy_col_idx = self._find_column(df, ['Policy'])
        if policy_col_idx is not None:
            policy_series = df.iloc[:, policy_col_idx]
            df = df[~policy_series.astype(str).str.strip().str.upper().eq('APPT. FEE')].copy()

        # Find the right column names (they may vary slightly)
        # Note: Order matters - more specific matches first, avoid generic fallbacks like 'Date'
        col_map = self._find_columns(df, {
            'group_no': ['Group No.', 'Bill Ctrl/', 'Group No'],
            'owner_name': ['Owner Name', 'Owner'],
            'payment_date': ['Payment Date', 'Payment'],
            'ptd': ['Paid To Date', 'Paid To'],
            'issue_date': ['Issue Date'],
            'premium': ['Premium'],
            'commission': ['Commission'],
            'advance_repay': ['Advance Repay', 'Advance'],
            'issue_state': ['Issue State'],
            'plan_description': ['Plan Description', 'Plan Desc'],
            'writing_agent': ['Writing Agent'],
        })

        output = pd.DataFrame()

        # PolicyNo - from Group No.
        output['PolicyNo'] = self._get_column(df, col_map['group_no'])

        # PHFirst - empty
        output['PHFirst'] = ''

        # PHLast - from Owner Name
        output['PHLast'] = self._get_column(df, col_map['owner_name'])

        # Status - hardcoded
        output['Status'] = 'Active'

        # Issuer - hardcoded
        output['Issuer'] = 'Manhattan Life'

        # State - from Issue State
        output['State'] = self._get_column(df, col_map['issue_state'])

        # ProductType - lookup from Plan Description
        plan_desc_col = self._get_column(df, col_map['plan_description'])
        output['ProductType'] = plan_desc_col.apply(
            lambda x: self.carrier_config.get_lookup(
                self.carrier_name, 'plan_to_product_type', str(x).strip()
            ) or ''
        )

        # PlanName - lookup from Plan Description
        output['PlanName'] = plan_desc_col.apply(
            lambda x: self.carrier_config.get_lookup(
                self.carrier_name, 'plan_to_plan_name', str(x).strip()
            ) or ''
        )

        # SubmittedDate - from Issue Date
        issue_date_col = self._get_column(df, col_map['issue_date'])
        output['SubmittedDate'] = self._format_date(issue_date_col)

        # EffectiveDate - from Issue Date
        output['EffectiveDate'] = self._format_date(issue_date_col)

        # TermDate - empty
        output['TermDate'] = ''

        # PaySched - hardcoded
        output['PaySched'] = 'Monthly'

        # PayCode - hardcoded
        output['PayCode'] = 'Default'

        # WritingAgentID - from Writing Agent
        output['WritingAgentID'] = self._get_column(df, col_map['writing_agent'])

        # Premium
        premium_col = self._get_column(df, col_map['premium'])
        output['Premium'] = premium_col

        # CommPrem - same as Premium
        output['CommPrem'] = premium_col

        # TranDate - from Payment Date
        output['TranDate'] = self._format_date(self._get_column(df, col_map['payment_date']))

        # CommReceived - IF(Commission <> 0, Commission, Advance Repay)
        commission = pd.to_numeric(self._get_column(df, col_map['commission']), errors='coerce').fillna(0)
        advance_repay = pd.to_numeric(self._get_column(df, col_map['advance_repay']), errors='coerce').fillna(0)
        output['CommReceived'] = commission.where(commission != 0, advance_repay)

        # PTD - from PTD column
        output['PTD'] = self._format_date(self._get_column(df, col_map['ptd']))

        # NoPayMon - hardcoded
        output['NoPayMon'] = 1

        # MemberCount - empty
        output['MemberCount'] = ''

        # Note - Plan Description
        output['Note'] = plan_desc_col

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
        output['PolicyNo'] = self._get_column(df, col_map['policy_number'])

        # Issuer - hardcoded
        output['Issuer'] = 'Manhattan Life'

        # CancelDate - from Paid To Date
        ptd_col = self._get_column(df, col_map['paid_to_date'])
        output['CancelDate'] = self._format_date(ptd_col)

        # ProcessDate - from Paid To Date
        output['ProcessDate'] = self._format_date(ptd_col)

        # PolicyStatus - hardcoded
        output['PolicyStatus'] = 'Chargeback'

        # Note - empty
        output['Note'] = ''

        return output

    def _transform_adjustment(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transform APPT. FEE rows to Commission Adjustments template."""
        df.columns = df.columns.str.strip()

        # Filter to only APPT. FEE rows
        policy_col_idx = self._find_column(df, ['Policy'])
        if policy_col_idx is None:
            return pd.DataFrame()

        policy_series = df.iloc[:, policy_col_idx]
        fee_df = df[policy_series.astype(str).str.strip().str.upper().eq('APPT. FEE')].copy()

        if len(fee_df) == 0:
            return pd.DataFrame()

        # Find the columns we need
        col_map = self._find_columns(fee_df, {
            'payor_name': ['Payor/Group Name', 'Payor', 'Group Name'],
            'charges': ['Charges/Transfers', 'Charges', 'Transfers'],
            'payment_date': ['Payment Date', 'Payment', 'Date'],
        })

        output = pd.DataFrame()

        # AgentID - Need to look up NPN from agent name in Payor/Group Name
        payor_col = self._get_column(fee_df, col_map['payor_name'])
        output['AgentID'] = payor_col.apply(self._lookup_npn)

        # ProcessDate - from Payment Date
        date_col = self._get_column(fee_df, col_map['payment_date'])
        output['ProcessDate'] = self._format_date(date_col)

        # Description - hardcoded "License Fee or Renewal"
        output['Description'] = 'License Fee or Renewal'

        # Issuer - hardcoded
        output['Issuer'] = 'Manhattan Life'

        # PolicyNo - empty for fee adjustments
        output['PolicyNo'] = ''

        # UnitPrice - empty
        output['UnitPrice'] = ''

        # Quantity - empty
        output['Quantity'] = ''

        # Total - invert the sign (negative fee -> positive adjustment)
        charges_col = self._get_column(fee_df, col_map['charges'])
        charges = pd.to_numeric(charges_col, errors='coerce').fillna(0)
        output['Total'] = -charges  # Invert: -40 becomes 40

        # ApplytoNet - Y
        output['ApplytoNet'] = 'Y'

        # ApplytoForm1099 - Y
        output['ApplytoForm1099'] = 'Y'

        # ApplytoAgentBalance - N
        output['ApplytoAgentBalance'] = 'N'

        # Note - include original agent name for reference
        output['Note'] = payor_col.apply(lambda x: f"Agent: {x}" if pd.notna(x) and str(x).strip() else '')

        return output

    def _find_columns(self, df: pd.DataFrame, column_map: Dict) -> Dict:
        """Find actual column names from possible variations. Returns column indices to handle duplicates."""
        result = {}
        df_cols = [c.strip() for c in df.columns]

        for key, possibilities in column_map.items():
            found_idx = None
            for poss in possibilities:
                # Exact match - find first occurrence by index
                for idx, col in enumerate(df_cols):
                    if col == poss:
                        found_idx = idx
                        break
                if found_idx is not None:
                    break
                # Partial match
                for idx, col in enumerate(df_cols):
                    if poss.lower() in col.lower():
                        found_idx = idx
                        break
                if found_idx is not None:
                    break

            if found_idx is not None:
                result[key] = found_idx
            else:
                # Use first possibility as default - try to find any match
                result[key] = possibilities[0]

        return result

    def _get_column(self, df: pd.DataFrame, col_ref) -> pd.Series:
        """Get a column from dataframe by index or name, always returning a Series."""
        if isinstance(col_ref, int):
            return df.iloc[:, col_ref]
        else:
            # If it's a name and there are duplicates, get first one
            col = df[col_ref]
            if isinstance(col, pd.DataFrame):
                return col.iloc[:, 0]
            return col

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
