from flask import Blueprint, render_template, request, jsonify, current_app, send_file
import os
import uuid
from werkzeug.utils import secure_filename
import pandas as pd
from app.file_parser import parse_file, get_file_preview
from app.carrier_recognition import CarrierRecognition
from app.carrier_configs import CarrierConfig
from app.transformers import get_transformer

main = Blueprint('main', __name__)

ALLOWED_EXTENSIONS = {'csv', 'xls', 'xlsx', 'xml'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@main.route('/')
def index():
    return render_template('index.html')


@main.route('/settings')
def settings():
    return render_template('settings.html')


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

        # Get carrier config to detect file type
        carrier_config = CarrierConfig(current_app.config['DATA_FOLDER'])
        carrier_config.initialize_default_configs()

        detected_file_type = None
        if recognized_carrier:
            detected_file_type = carrier_config.detect_file_type(recognized_carrier, columns)

        # Get configured carriers
        configured_carriers = carrier_config.get_all_carriers()

        return jsonify({
            'success': True,
            'file_id': unique_id,
            'filename': filename,
            'saved_filename': saved_filename,
            'columns': columns,
            'preview': preview_data,
            'row_count': len(parse_file(filepath)),
            'recognized_carrier': recognized_carrier,
            'known_carriers': recognition.get_all_carriers(),
            'configured_carriers': configured_carriers,
            'detected_file_type': detected_file_type
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
    file_type = data.get('file_type', 'commission')

    if not carrier_name or not saved_filename:
        return jsonify({'error': 'Missing required fields'}), 400

    # Register carrier signature
    recognition = CarrierRecognition(current_app.config['DATA_FOLDER'])
    recognition.register_carrier(carrier_name, columns, original_filename)

    # Check if carrier has a transformer configured
    carrier_config = CarrierConfig(current_app.config['DATA_FOLDER'])
    has_transformer = get_transformer(carrier_name, carrier_config) is not None

    return jsonify({
        'success': True,
        'message': f'Carrier "{carrier_name}" registered successfully',
        'has_transformer': has_transformer,
        'file_type': file_type
    })


@main.route('/api/carriers', methods=['GET'])
def get_carriers():
    """Get list of all known carriers."""
    recognition = CarrierRecognition(current_app.config['DATA_FOLDER'])
    carrier_config = CarrierConfig(current_app.config['DATA_FOLDER'])
    return jsonify({
        'carriers': recognition.get_all_carriers(),
        'configured_carriers': carrier_config.get_all_carriers()
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
    file_type = data.get('file_type', 'commission')
    use_transformer = data.get('use_transformer', True)
    column_mappings = data.get('column_mappings', {})

    if not saved_filename or not carrier_name:
        return jsonify({'error': 'Missing required fields'}), 400

    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], saved_filename)
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404

    try:
        # Parse the uploaded file
        df = parse_file(filepath)

        # Get carrier config
        carrier_config = CarrierConfig(current_app.config['DATA_FOLDER'])
        transformer = get_transformer(carrier_name, carrier_config)

        if transformer and use_transformer:
            # Use the carrier-specific transformer
            output_df = transformer.transform(df, file_type)

            # Determine template based on file type
            config = carrier_config.get_carrier_config(carrier_name)
            if config and file_type in config.get('file_types', {}):
                template_name = config['file_types'][file_type]['template']
            else:
                template_name = 'Policy And Transactions Template (13).csv'

            # Check for missing lookups
            missing_lookups = []
            if file_type == 'commission':
                # Find any rows where ProductType or PlanName is empty but Note has a value
                for idx, row in output_df.iterrows():
                    if (row.get('ProductType', '') == '' or row.get('PlanName', '') == '') and row.get('Note', '') != '':
                        plan_desc = row.get('Note', '')
                        if plan_desc and plan_desc not in missing_lookups:
                            missing_lookups.append(plan_desc)
        else:
            # Fallback to manual column mapping
            template_name = data.get('template', 'Policy And Transactions Template (13).csv')
            template_path = os.path.join(current_app.config['TEMPLATES_FOLDER'], template_name)
            template_df = pd.read_csv(template_path, nrows=0)
            target_columns = list(template_df.columns)

            output_df = pd.DataFrame(columns=target_columns)
            for target_col, source_col in column_mappings.items():
                if source_col and source_col in df.columns:
                    output_df[target_col] = df[source_col]

            for col in target_columns:
                if col not in output_df.columns or output_df[col].isna().all():
                    output_df[col] = ''

            missing_lookups = []

        # Generate export file
        timestamp = pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')
        export_filename = f"{carrier_name}_{file_type}_{timestamp}.csv"
        export_path = os.path.join(current_app.config['EXPORT_FOLDER'], export_filename)
        output_df.to_csv(export_path, index=False)

        return jsonify({
            'success': True,
            'export_filename': export_filename,
            'row_count': len(output_df),
            'missing_lookups': missing_lookups[:10]  # Limit to first 10
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@main.route('/api/available-outputs', methods=['POST'])
def get_available_outputs():
    """Check what output types are available for a file."""
    data = request.json
    saved_filename = data.get('saved_filename')
    carrier_name = data.get('carrier_name')

    if not saved_filename or not carrier_name:
        return jsonify({'error': 'Missing required fields'}), 400

    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], saved_filename)
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404

    try:
        df = parse_file(filepath)
        carrier_config = CarrierConfig(current_app.config['DATA_FOLDER'])
        transformer = get_transformer(carrier_name, carrier_config)

        if transformer:
            available = transformer.get_available_outputs(df)
        else:
            available = ['commission']

        # Map output types to display names
        output_info = {
            'commission': {'name': 'Commission', 'template': 'Policy And Transactions'},
            'chargeback': {'name': 'Chargeback', 'template': 'Commission Chargebacks'},
            'adjustment': {'name': 'Adjustment (Fees)', 'template': 'Commission Adjustments'}
        }

        outputs = []
        for out_type in available:
            info = output_info.get(out_type, {'name': out_type.title(), 'template': 'Unknown'})
            outputs.append({
                'type': out_type,
                'name': info['name'],
                'template': info['template']
            })

        return jsonify({
            'success': True,
            'available_outputs': outputs
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@main.route('/api/process-all', methods=['POST'])
def process_all_outputs():
    """Process file and generate all available output types."""
    data = request.json
    saved_filename = data.get('saved_filename')
    carrier_name = data.get('carrier_name')
    output_types = data.get('output_types', [])  # List of types to generate

    if not saved_filename or not carrier_name:
        return jsonify({'error': 'Missing required fields'}), 400

    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], saved_filename)
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404

    try:
        df = parse_file(filepath)
        carrier_config = CarrierConfig(current_app.config['DATA_FOLDER'])
        transformer = get_transformer(carrier_name, carrier_config)

        if not transformer:
            return jsonify({'error': 'No transformer configured for this carrier'}), 400

        timestamp = pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')
        results = []
        all_missing_lookups = []

        for file_type in output_types:
            try:
                output_df = transformer.transform(df, file_type)

                if len(output_df) == 0:
                    continue

                # Generate export file
                export_filename = f"{carrier_name}_{file_type}_{timestamp}.csv"
                export_path = os.path.join(current_app.config['EXPORT_FOLDER'], export_filename)
                output_df.to_csv(export_path, index=False)

                # Check for missing lookups (commission only)
                if file_type == 'commission':
                    for idx, row in output_df.iterrows():
                        if (row.get('ProductType', '') == '' or row.get('PlanName', '') == '') and row.get('Note', '') != '':
                            plan_desc = row.get('Note', '')
                            if plan_desc and plan_desc not in all_missing_lookups:
                                all_missing_lookups.append(plan_desc)

                results.append({
                    'type': file_type,
                    'filename': export_filename,
                    'row_count': len(output_df)
                })
            except Exception as e:
                print(f"Error processing {file_type}: {e}")
                continue

        return jsonify({
            'success': True,
            'results': results,
            'missing_lookups': all_missing_lookups[:10]
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@main.route('/api/download/<filename>')
def download_file(filename):
    """Download exported file."""
    export_path = os.path.join(current_app.config['EXPORT_FOLDER'], filename)
    if not os.path.exists(export_path):
        return jsonify({'error': 'File not found'}), 404
    return send_file(export_path, as_attachment=True)


# ==================== LOOKUP MANAGEMENT ====================

@main.route('/api/lookups/<carrier_name>', methods=['GET'])
def get_lookups(carrier_name):
    """Get all lookups for a carrier."""
    carrier_config = CarrierConfig(current_app.config['DATA_FOLDER'])
    lookups = carrier_config.get_all_lookups(carrier_name)
    return jsonify({'lookups': lookups})


@main.route('/api/lookups/<carrier_name>/<lookup_name>', methods=['POST'])
def update_lookup(carrier_name, lookup_name):
    """Update or add a lookup entry."""
    data = request.json
    key = data.get('key')
    value = data.get('value')

    if not key or not value:
        return jsonify({'error': 'Key and value are required'}), 400

    carrier_config = CarrierConfig(current_app.config['DATA_FOLDER'])
    carrier_config.update_lookup(carrier_name, lookup_name, key, value)

    return jsonify({'success': True})


@main.route('/api/lookups/<carrier_name>/<lookup_name>/<path:key>', methods=['DELETE'])
def delete_lookup(carrier_name, lookup_name, key):
    """Delete a lookup entry."""
    carrier_config = CarrierConfig(current_app.config['DATA_FOLDER'])
    carrier_config.delete_lookup_entry(carrier_name, lookup_name, key)
    return jsonify({'success': True})


@main.route('/api/carrier-config/<carrier_name>', methods=['GET'])
def get_carrier_config(carrier_name):
    """Get full configuration for a carrier."""
    carrier_config = CarrierConfig(current_app.config['DATA_FOLDER'])
    config = carrier_config.get_carrier_config(carrier_name)
    if not config:
        return jsonify({'error': 'Carrier not found'}), 404
    return jsonify({'config': config})
