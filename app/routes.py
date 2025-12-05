from flask import Blueprint, render_template, request, jsonify, current_app, send_file
import os
import uuid
from werkzeug.utils import secure_filename
from app.file_parser import parse_file, get_file_preview
from app.carrier_recognition import CarrierRecognition

main = Blueprint('main', __name__)

ALLOWED_EXTENSIONS = {'csv', 'xls', 'xlsx', 'xml'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@main.route('/')
def index():
    return render_template('index.html')


@main.route('/api/upload', methods=['POST'])
def upload_file():
    """Handle file upload and return preview data."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Allowed: CSV, XLS, XLSX, XML'}), 400

    # Save file with unique name
    filename = secure_filename(file.filename)
    unique_id = str(uuid.uuid4())[:8]
    saved_filename = f"{unique_id}_{filename}"
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], saved_filename)
    file.save(filepath)

    try:
        # Get preview data
        preview_data, columns = get_file_preview(filepath, rows=10)

        # Try to recognize carrier
        recognition = CarrierRecognition(current_app.config['DATA_FOLDER'])
        recognized_carrier = recognition.recognize_carrier(columns, filename)

        return jsonify({
            'success': True,
            'file_id': unique_id,
            'filename': filename,
            'saved_filename': saved_filename,
            'columns': columns,
            'preview': preview_data,
            'row_count': len(parse_file(filepath)),
            'recognized_carrier': recognized_carrier,
            'known_carriers': recognition.get_all_carriers()
        })
    except Exception as e:
        # Clean up file on error
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'error': str(e)}), 500


@main.route('/api/confirm-carrier', methods=['POST'])
def confirm_carrier():
    """Confirm carrier selection and register for future recognition."""
    data = request.json
    carrier_name = data.get('carrier_name')
    saved_filename = data.get('saved_filename')
    columns = data.get('columns', [])
    original_filename = data.get('original_filename', '')

    if not carrier_name or not saved_filename:
        return jsonify({'error': 'Missing required fields'}), 400

    # Register carrier signature
    recognition = CarrierRecognition(current_app.config['DATA_FOLDER'])
    recognition.register_carrier(carrier_name, columns, original_filename)

    return jsonify({
        'success': True,
        'message': f'Carrier "{carrier_name}" registered successfully'
    })


@main.route('/api/carriers', methods=['GET'])
def get_carriers():
    """Get list of all known carriers."""
    recognition = CarrierRecognition(current_app.config['DATA_FOLDER'])
    return jsonify({
        'carriers': recognition.get_all_carriers()
    })


@main.route('/api/templates', methods=['GET'])
def get_templates():
    """Get list of available export templates."""
    templates_folder = current_app.config['TEMPLATES_FOLDER']
    templates = []
    for f in os.listdir(templates_folder):
        if f.endswith('.csv'):
            templates.append(f)
    return jsonify({'templates': templates})


@main.route('/api/process', methods=['POST'])
def process_file():
    """Process uploaded file and generate export."""
    data = request.json
    saved_filename = data.get('saved_filename')
    carrier_name = data.get('carrier_name')
    template_name = data.get('template', 'Policy And Transactions Template (13).csv')
    column_mappings = data.get('column_mappings', {})

    if not saved_filename or not carrier_name:
        return jsonify({'error': 'Missing required fields'}), 400

    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], saved_filename)
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404

    try:
        # Parse the uploaded file
        df = parse_file(filepath)

        # Load template to get target columns
        template_path = os.path.join(current_app.config['TEMPLATES_FOLDER'], template_name)
        import pandas as pd
        template_df = pd.read_csv(template_path, nrows=0)
        target_columns = list(template_df.columns)

        # Create output dataframe with template columns
        output_df = pd.DataFrame(columns=target_columns)

        # Apply column mappings
        for target_col, source_col in column_mappings.items():
            if source_col and source_col in df.columns:
                output_df[target_col] = df[source_col]

        # Fill unmapped columns with empty strings
        for col in target_columns:
            if col not in output_df.columns or output_df[col].isna().all():
                output_df[col] = ''

        # Generate export file
        export_filename = f"{carrier_name}_{saved_filename.replace('.', '_')}_export.csv"
        export_path = os.path.join(current_app.config['EXPORT_FOLDER'], export_filename)
        output_df.to_csv(export_path, index=False)

        return jsonify({
            'success': True,
            'export_filename': export_filename,
            'row_count': len(output_df)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@main.route('/api/download/<filename>')
def download_file(filename):
    """Download exported file."""
    export_path = os.path.join(current_app.config['EXPORT_FOLDER'], filename)
    if not os.path.exists(export_path):
        return jsonify({'error': 'File not found'}), 404
    return send_file(export_path, as_attachment=True)
