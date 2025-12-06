"""
Database models for Commission Processor.
Designed to work with SQLite locally and PostgreSQL/MySQL on AWS.
"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Carrier(db.Model):
    """Carrier/Insurance company."""
    __tablename__ = 'carriers'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    policies = db.relationship('Policy', backref='carrier', lazy='dynamic')
    commissions = db.relationship('Commission', backref='carrier', lazy='dynamic')
    chargebacks = db.relationship('Chargeback', backref='carrier', lazy='dynamic')
    adjustments = db.relationship('Adjustment', backref='carrier', lazy='dynamic')

    def __repr__(self):
        return f'<Carrier {self.name}>'


class Agent(db.Model):
    """Agent/Producer."""
    __tablename__ = 'agents'

    id = db.Column(db.Integer, primary_key=True)
    npn = db.Column(db.String(20), unique=True, nullable=True)  # National Producer Number
    writing_agent_id = db.Column(db.String(50), nullable=True)
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    commissions = db.relationship('Commission', backref='agent', lazy='dynamic')
    adjustments = db.relationship('Adjustment', backref='agent', lazy='dynamic')

    def __repr__(self):
        return f'<Agent {self.first_name} {self.last_name}>'


class Policy(db.Model):
    """Policy record - master record for a policy."""
    __tablename__ = 'policies'

    id = db.Column(db.Integer, primary_key=True)
    policy_no = db.Column(db.String(50), nullable=False)
    carrier_id = db.Column(db.Integer, db.ForeignKey('carriers.id'), nullable=False)

    # Policyholder info
    ph_first = db.Column(db.String(100))
    ph_last = db.Column(db.String(100))

    # Policy details
    status = db.Column(db.String(50))
    state = db.Column(db.String(10))
    product_type = db.Column(db.String(100))
    plan_name = db.Column(db.String(200))

    # Dates
    submitted_date = db.Column(db.Date)
    effective_date = db.Column(db.Date)
    term_date = db.Column(db.Date)

    # Payment info
    pay_sched = db.Column(db.String(50))
    pay_code = db.Column(db.String(50))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    commissions = db.relationship('Commission', backref='policy', lazy='dynamic')
    chargebacks = db.relationship('Chargeback', backref='policy', lazy='dynamic')

    # Unique constraint on policy_no + carrier
    __table_args__ = (
        db.UniqueConstraint('policy_no', 'carrier_id', name='uix_policy_carrier'),
    )

    def __repr__(self):
        return f'<Policy {self.policy_no}>'


class Commission(db.Model):
    """Commission transaction record."""
    __tablename__ = 'commissions'

    id = db.Column(db.Integer, primary_key=True)
    policy_id = db.Column(db.Integer, db.ForeignKey('policies.id'), nullable=True)
    carrier_id = db.Column(db.Integer, db.ForeignKey('carriers.id'), nullable=False)
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'), nullable=True)

    # From template fields
    policy_no = db.Column(db.String(50))
    writing_agent_id = db.Column(db.String(50))
    premium = db.Column(db.Numeric(12, 2))
    comm_prem = db.Column(db.Numeric(12, 2))
    tran_date = db.Column(db.Date)
    comm_received = db.Column(db.Numeric(12, 2))
    ptd = db.Column(db.Date)  # Paid Through Date
    no_pay_mon = db.Column(db.Integer)
    member_count = db.Column(db.Integer)
    note = db.Column(db.Text)

    # Metadata
    source_file = db.Column(db.String(255))  # Original filename
    import_batch = db.Column(db.String(50))  # Batch ID for grouping imports
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Commission {self.policy_no} ${self.comm_received}>'


class Chargeback(db.Model):
    """Chargeback record."""
    __tablename__ = 'chargebacks'

    id = db.Column(db.Integer, primary_key=True)
    policy_id = db.Column(db.Integer, db.ForeignKey('policies.id'), nullable=True)
    carrier_id = db.Column(db.Integer, db.ForeignKey('carriers.id'), nullable=False)

    # From template fields
    policy_no = db.Column(db.String(50))
    cancel_date = db.Column(db.Date)
    process_date = db.Column(db.Date)
    policy_status = db.Column(db.String(50))
    note = db.Column(db.Text)

    # Metadata
    source_file = db.Column(db.String(255))
    import_batch = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Chargeback {self.policy_no}>'


class Adjustment(db.Model):
    """Adjustment/Fee record."""
    __tablename__ = 'adjustments'

    id = db.Column(db.Integer, primary_key=True)
    carrier_id = db.Column(db.Integer, db.ForeignKey('carriers.id'), nullable=False)
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'), nullable=True)

    # From template fields
    agent_npn = db.Column(db.String(20))
    process_date = db.Column(db.Date)
    description = db.Column(db.String(255))
    policy_no = db.Column(db.String(50))
    unit_price = db.Column(db.Numeric(12, 2))
    quantity = db.Column(db.Integer)
    total = db.Column(db.Numeric(12, 2))
    apply_to_net = db.Column(db.String(1))
    apply_to_form_1099 = db.Column(db.String(1))
    apply_to_agent_balance = db.Column(db.String(1))
    note = db.Column(db.Text)

    # Metadata
    source_file = db.Column(db.String(255))
    import_batch = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Adjustment {self.description} ${self.total}>'


class ImportLog(db.Model):
    """Log of file imports for tracking and auditing."""
    __tablename__ = 'import_logs'

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.String(50), unique=True, nullable=False)
    carrier_name = db.Column(db.String(100))
    file_name = db.Column(db.String(255))
    file_type = db.Column(db.String(50))  # commission, chargeback, adjustment
    source = db.Column(db.String(50))  # 'manual', 'google_drive', 'api'

    # Stats
    rows_processed = db.Column(db.Integer, default=0)
    rows_imported = db.Column(db.Integer, default=0)
    rows_skipped = db.Column(db.Integer, default=0)
    errors = db.Column(db.Text)  # JSON list of errors

    # Status
    status = db.Column(db.String(20), default='pending')  # pending, processing, completed, failed
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<ImportLog {self.batch_id} {self.status}>'


class DriveConfig(db.Model):
    """Configuration for Google Drive integration."""
    __tablename__ = 'drive_configs'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # e.g., "Manhattan Life Inbox"
    carrier_name = db.Column(db.String(100))

    # Google Drive folder IDs
    input_folder_id = db.Column(db.String(100))
    output_folder_id = db.Column(db.String(100))
    processed_folder_id = db.Column(db.String(100))  # Move files here after processing

    # Settings
    auto_process = db.Column(db.Boolean, default=False)
    file_pattern = db.Column(db.String(100))  # Optional regex pattern to match files
    is_active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<DriveConfig {self.name}>'
