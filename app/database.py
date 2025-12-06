"""
Database service layer for Commission Processor.
Handles saving transformed data to the database.
"""
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import uuid

from app.models import (
    db, Carrier, Agent, Policy, Commission, Chargeback, Adjustment, ImportLog
)


class DatabaseService:
    """Service for database operations."""

    @staticmethod
    def get_or_create_carrier(name: str) -> Carrier:
        """Get existing carrier or create new one."""
        carrier = Carrier.query.filter_by(name=name).first()
        if not carrier:
            carrier = Carrier(name=name)
            db.session.add(carrier)
            db.session.commit()
        return carrier

    @staticmethod
    def get_or_create_agent(npn: str = None, writing_agent_id: str = None,
                            first_name: str = None, last_name: str = None) -> Optional[Agent]:
        """Get existing agent or create new one."""
        if not npn and not writing_agent_id:
            return None

        # Try to find by NPN first
        agent = None
        if npn:
            agent = Agent.query.filter_by(npn=npn).first()
        if not agent and writing_agent_id:
            agent = Agent.query.filter_by(writing_agent_id=writing_agent_id).first()

        if not agent:
            agent = Agent(
                npn=npn,
                writing_agent_id=writing_agent_id,
                first_name=first_name,
                last_name=last_name
            )
            db.session.add(agent)
            db.session.commit()

        return agent

    @staticmethod
    def parse_date(val) -> Optional[datetime]:
        """Parse various date formats to datetime."""
        if pd.isna(val) or val == '' or val is None:
            return None
        try:
            if isinstance(val, datetime):
                return val
            return pd.to_datetime(val).to_pydatetime()
        except:
            return None

    @staticmethod
    def parse_decimal(val) -> Optional[float]:
        """Parse numeric value."""
        if pd.isna(val) or val == '' or val is None:
            return None
        try:
            return float(val)
        except:
            return None

    def save_commissions(self, df: pd.DataFrame, carrier_name: str,
                         source_file: str = None, source: str = 'manual') -> Dict:
        """
        Save commission data to database.

        Args:
            df: DataFrame with commission data (in template format)
            carrier_name: Name of the carrier
            source_file: Original filename
            source: Source of import ('manual', 'google_drive', 'api')

        Returns:
            Dict with import stats
        """
        batch_id = str(uuid.uuid4())[:8]
        carrier = self.get_or_create_carrier(carrier_name)

        # Create import log
        import_log = ImportLog(
            batch_id=batch_id,
            carrier_name=carrier_name,
            file_name=source_file,
            file_type='commission',
            source=source,
            rows_processed=len(df),
            status='processing',
            started_at=datetime.utcnow()
        )
        db.session.add(import_log)
        db.session.commit()

        imported = 0
        skipped = 0
        errors = []

        for idx, row in df.iterrows():
            try:
                commission = Commission(
                    carrier_id=carrier.id,
                    policy_no=str(row.get('PolicyNo', '')).strip(),
                    writing_agent_id=str(row.get('WritingAgentID', '')).strip(),
                    premium=self.parse_decimal(row.get('Premium')),
                    comm_prem=self.parse_decimal(row.get('CommPrem')),
                    tran_date=self.parse_date(row.get('TranDate')),
                    comm_received=self.parse_decimal(row.get('CommReceived')),
                    ptd=self.parse_date(row.get('PTD')),
                    no_pay_mon=int(row.get('NoPayMon', 0)) if row.get('NoPayMon') else None,
                    member_count=int(row.get('MemberCount', 0)) if row.get('MemberCount') else None,
                    note=str(row.get('Note', '')).strip() if row.get('Note') else None,
                    source_file=source_file,
                    import_batch=batch_id
                )
                db.session.add(commission)
                imported += 1
            except Exception as e:
                errors.append(f"Row {idx}: {str(e)}")
                skipped += 1

        db.session.commit()

        # Update import log
        import_log.rows_imported = imported
        import_log.rows_skipped = skipped
        import_log.errors = str(errors) if errors else None
        import_log.status = 'completed'
        import_log.completed_at = datetime.utcnow()
        db.session.commit()

        return {
            'batch_id': batch_id,
            'imported': imported,
            'skipped': skipped,
            'errors': errors[:10]  # First 10 errors
        }

    def save_chargebacks(self, df: pd.DataFrame, carrier_name: str,
                         source_file: str = None, source: str = 'manual') -> Dict:
        """Save chargeback data to database."""
        batch_id = str(uuid.uuid4())[:8]
        carrier = self.get_or_create_carrier(carrier_name)

        import_log = ImportLog(
            batch_id=batch_id,
            carrier_name=carrier_name,
            file_name=source_file,
            file_type='chargeback',
            source=source,
            rows_processed=len(df),
            status='processing',
            started_at=datetime.utcnow()
        )
        db.session.add(import_log)
        db.session.commit()

        imported = 0
        skipped = 0
        errors = []

        for idx, row in df.iterrows():
            try:
                chargeback = Chargeback(
                    carrier_id=carrier.id,
                    policy_no=str(row.get('PolicyNo', '')).strip(),
                    cancel_date=self.parse_date(row.get('CancelDate')),
                    process_date=self.parse_date(row.get('ProcessDate')),
                    policy_status=str(row.get('PolicyStatus', '')).strip(),
                    note=str(row.get('Note', '')).strip() if row.get('Note') else None,
                    source_file=source_file,
                    import_batch=batch_id
                )
                db.session.add(chargeback)
                imported += 1
            except Exception as e:
                errors.append(f"Row {idx}: {str(e)}")
                skipped += 1

        db.session.commit()

        import_log.rows_imported = imported
        import_log.rows_skipped = skipped
        import_log.errors = str(errors) if errors else None
        import_log.status = 'completed'
        import_log.completed_at = datetime.utcnow()
        db.session.commit()

        return {
            'batch_id': batch_id,
            'imported': imported,
            'skipped': skipped,
            'errors': errors[:10]
        }

    def save_adjustments(self, df: pd.DataFrame, carrier_name: str,
                         source_file: str = None, source: str = 'manual') -> Dict:
        """Save adjustment data to database."""
        batch_id = str(uuid.uuid4())[:8]
        carrier = self.get_or_create_carrier(carrier_name)

        import_log = ImportLog(
            batch_id=batch_id,
            carrier_name=carrier_name,
            file_name=source_file,
            file_type='adjustment',
            source=source,
            rows_processed=len(df),
            status='processing',
            started_at=datetime.utcnow()
        )
        db.session.add(import_log)
        db.session.commit()

        imported = 0
        skipped = 0
        errors = []

        for idx, row in df.iterrows():
            try:
                adjustment = Adjustment(
                    carrier_id=carrier.id,
                    agent_npn=str(row.get('AgentID', '')).strip(),
                    process_date=self.parse_date(row.get('ProcessDate')),
                    description=str(row.get('Description', '')).strip(),
                    policy_no=str(row.get('PolicyNo', '')).strip() if row.get('PolicyNo') else None,
                    unit_price=self.parse_decimal(row.get('UnitPrice')),
                    quantity=int(row.get('Quantity', 0)) if row.get('Quantity') else None,
                    total=self.parse_decimal(row.get('Total')),
                    apply_to_net=str(row.get('ApplytoNet', '')).strip(),
                    apply_to_form_1099=str(row.get('ApplytoForm1099', '')).strip(),
                    apply_to_agent_balance=str(row.get('ApplytoAgentBalance', '')).strip(),
                    note=str(row.get('Note', '')).strip() if row.get('Note') else None,
                    source_file=source_file,
                    import_batch=batch_id
                )
                db.session.add(adjustment)
                imported += 1
            except Exception as e:
                errors.append(f"Row {idx}: {str(e)}")
                skipped += 1

        db.session.commit()

        import_log.rows_imported = imported
        import_log.rows_skipped = skipped
        import_log.errors = str(errors) if errors else None
        import_log.status = 'completed'
        import_log.completed_at = datetime.utcnow()
        db.session.commit()

        return {
            'batch_id': batch_id,
            'imported': imported,
            'skipped': skipped,
            'errors': errors[:10]
        }

    def get_import_history(self, limit: int = 50) -> List[ImportLog]:
        """Get recent import history."""
        return ImportLog.query.order_by(ImportLog.created_at.desc()).limit(limit).all()

    def export_combined_commissions(self, carrier_name: str = None,
                                    start_date: datetime = None,
                                    end_date: datetime = None) -> pd.DataFrame:
        """Export commissions as combined DataFrame."""
        query = Commission.query

        if carrier_name:
            carrier = Carrier.query.filter_by(name=carrier_name).first()
            if carrier:
                query = query.filter_by(carrier_id=carrier.id)

        if start_date:
            query = query.filter(Commission.tran_date >= start_date)
        if end_date:
            query = query.filter(Commission.tran_date <= end_date)

        records = query.all()

        data = []
        for c in records:
            data.append({
                'PolicyNo': c.policy_no,
                'Issuer': c.carrier.name if c.carrier else '',
                'WritingAgentID': c.writing_agent_id,
                'Premium': c.premium,
                'CommPrem': c.comm_prem,
                'TranDate': c.tran_date,
                'CommReceived': c.comm_received,
                'PTD': c.ptd,
                'NoPayMon': c.no_pay_mon,
                'MemberCount': c.member_count,
                'Note': c.note,
                'SourceFile': c.source_file,
                'ImportBatch': c.import_batch,
                'ImportedAt': c.created_at
            })

        return pd.DataFrame(data)

    def export_combined_chargebacks(self, carrier_name: str = None) -> pd.DataFrame:
        """Export chargebacks as combined DataFrame."""
        query = Chargeback.query

        if carrier_name:
            carrier = Carrier.query.filter_by(name=carrier_name).first()
            if carrier:
                query = query.filter_by(carrier_id=carrier.id)

        records = query.all()

        data = []
        for c in records:
            data.append({
                'PolicyNo': c.policy_no,
                'Issuer': c.carrier.name if c.carrier else '',
                'CancelDate': c.cancel_date,
                'ProcessDate': c.process_date,
                'PolicyStatus': c.policy_status,
                'Note': c.note,
                'SourceFile': c.source_file,
                'ImportBatch': c.import_batch,
                'ImportedAt': c.created_at
            })

        return pd.DataFrame(data)

    def export_combined_adjustments(self, carrier_name: str = None) -> pd.DataFrame:
        """Export adjustments as combined DataFrame."""
        query = Adjustment.query

        if carrier_name:
            carrier = Carrier.query.filter_by(name=carrier_name).first()
            if carrier:
                query = query.filter_by(carrier_id=carrier.id)

        records = query.all()

        data = []
        for a in records:
            data.append({
                'AgentID': a.agent_npn,
                'ProcessDate': a.process_date,
                'Description': a.description,
                'Issuer': a.carrier.name if a.carrier else '',
                'PolicyNo': a.policy_no,
                'UnitPrice': a.unit_price,
                'Quantity': a.quantity,
                'Total': a.total,
                'ApplytoNet': a.apply_to_net,
                'ApplytoForm1099': a.apply_to_form_1099,
                'ApplytoAgentBalance': a.apply_to_agent_balance,
                'Note': a.note,
                'SourceFile': a.source_file,
                'ImportBatch': a.import_batch,
                'ImportedAt': a.created_at
            })

        return pd.DataFrame(data)


# Global instance
db_service = DatabaseService()
