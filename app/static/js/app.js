// State
let currentFile = null;
let currentColumns = [];
let savedFilename = '';
let carrierName = '';
let fileType = 'commission';
let hasTransformer = false;
let availableOutputs = [];
let exportResults = [];

// DOM Elements
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const loading = document.getElementById('loading');
const previewSection = document.getElementById('previewSection');
const exportSection = document.getElementById('exportSection');
const carrierModal = document.getElementById('carrierModal');

// Template columns (Policy And Transactions Template)
const templateColumns = [
    'PolicyNo', 'PHFirst', 'PHLast', 'Status', 'Issuer', 'State', 'ProductType',
    'PlanName', 'SubmittedDate', 'EffectiveDate', 'TermDate', 'PaySched', 'PayCode',
    'WritingAgentID', 'Premium', 'CommPrem', 'TranDate', 'CommReceived', 'PTD',
    'NoPayMon', 'MemberCount', 'Note'
];

// Event Listeners
dropZone.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('dragover', handleDragOver);
dropZone.addEventListener('dragleave', handleDragLeave);
dropZone.addEventListener('drop', handleDrop);
fileInput.addEventListener('change', handleFileSelect);

document.getElementById('processBtn').addEventListener('click', processFile);
document.getElementById('cancelBtn').addEventListener('click', resetUI);
document.getElementById('newUploadBtn').addEventListener('click', resetUI);
document.getElementById('confirmCarrierBtn').addEventListener('click', confirmCarrier);
document.getElementById('cancelCarrierBtn').addEventListener('click', () => {
    carrierModal.classList.add('hidden');
    resetUI();
});

// Drag and Drop Handlers
function handleDragOver(e) {
    e.preventDefault();
    dropZone.classList.add('dragover');
}

function handleDragLeave(e) {
    e.preventDefault();
    dropZone.classList.remove('dragover');
}

function handleDrop(e) {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        uploadFile(files[0]);
    }
}

function handleFileSelect(e) {
    if (e.target.files.length > 0) {
        uploadFile(e.target.files[0]);
    }
}

// Upload File
async function uploadFile(file) {
    currentFile = file;
    showLoading(true);

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        showLoading(false);

        if (data.error) {
            alert('Error: ' + data.error);
            return;
        }

        currentColumns = data.columns;
        savedFilename = data.saved_filename;

        // Populate known carriers in modal (combine all carriers)
        const allCarriers = [...new Set([
            ...(data.known_carriers || []),
            ...(data.configured_carriers || [])
        ])].sort();

        // Set detected file type if available
        if (data.detected_file_type) {
            document.getElementById('fileTypeSelect').value = data.detected_file_type;
        }

        const modalTitle = document.getElementById('carrierModalTitle');
        const modalMessage = document.getElementById('carrierModalMessage');
        const carrierSelect = document.getElementById('carrierNameSelect');

        if (data.recognized_carrier) {
            // Carrier recognized - pre-select in dropdown
            modalTitle.textContent = 'Confirm Carrier & File Type';
            modalMessage.textContent = `Recognized carrier: "${data.recognized_carrier}". Please confirm:`;
            populateCarrierDropdown(allCarriers, data.recognized_carrier);
        } else {
            // Unknown carrier - ask for name with helpful message
            modalTitle.textContent = "I don't recognize this file";
            modalMessage.textContent = 'What carrier is this file for?';
            populateCarrierDropdown(allCarriers, null);
        }

        // Show carrier modal
        carrierModal.classList.remove('hidden');
        carrierSelect.focus();

        // Store preview data for later
        currentFile.previewData = data;

    } catch (error) {
        showLoading(false);
        alert('Error uploading file: ' + error.message);
    }
}

function populateCarrierDropdown(carriers, recognizedCarrier = null) {
    const select = document.getElementById('carrierNameSelect');
    const newCarrierGroup = document.getElementById('newCarrierGroup');
    const newCarrierInput = document.getElementById('newCarrierInput');

    // Reset
    select.innerHTML = '<option value="">-- Select Carrier --</option>';
    newCarrierGroup.classList.add('hidden');
    newCarrierInput.value = '';

    // Add existing carriers
    carriers.forEach(carrier => {
        const option = document.createElement('option');
        option.value = carrier;
        option.textContent = carrier;
        select.appendChild(option);
    });

    // Add "Add new carrier..." option at the end
    const newOption = document.createElement('option');
    newOption.value = '__new__';
    newOption.textContent = '+ Add new carrier...';
    select.appendChild(newOption);

    // If carrier was recognized, pre-select it
    if (recognizedCarrier && carriers.includes(recognizedCarrier)) {
        select.value = recognizedCarrier;
    }

    // Handle dropdown change
    select.onchange = function() {
        if (this.value === '__new__') {
            newCarrierGroup.classList.remove('hidden');
            newCarrierInput.focus();
        } else {
            newCarrierGroup.classList.add('hidden');
            newCarrierInput.value = '';
        }
    };
}

async function confirmCarrier() {
    const select = document.getElementById('carrierNameSelect');
    const newCarrierInput = document.getElementById('newCarrierInput');
    fileType = document.getElementById('fileTypeSelect').value;

    // Get carrier name from dropdown or new input
    if (select.value === '__new__') {
        carrierName = newCarrierInput.value.trim();
        if (!carrierName) {
            alert('Please enter a carrier name');
            newCarrierInput.focus();
            return;
        }
    } else {
        carrierName = select.value;
        if (!carrierName) {
            alert('Please select a carrier');
            return;
        }
    }

    // Register carrier
    const response = await fetch('/api/confirm-carrier', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            carrier_name: carrierName,
            saved_filename: savedFilename,
            columns: currentColumns,
            original_filename: currentFile.name,
            file_type: fileType
        })
    });

    const data = await response.json();
    hasTransformer = data.has_transformer;

    carrierModal.classList.add('hidden');

    // Check for available output types
    if (hasTransformer) {
        await checkAvailableOutputs();
    }

    showPreview(currentFile.previewData);
}

async function checkAvailableOutputs() {
    try {
        const response = await fetch('/api/available-outputs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                saved_filename: savedFilename,
                carrier_name: carrierName
            })
        });

        const data = await response.json();
        if (data.success) {
            availableOutputs = data.available_outputs;
        }
    } catch (error) {
        console.error('Error checking available outputs:', error);
        availableOutputs = [{ type: 'commission', name: 'Commission', template: 'Policy And Transactions' }];
    }
}

function showPreview(data) {
    document.getElementById('previewFilename').textContent = `${data.filename} (${carrierName})`;
    document.getElementById('rowCount').textContent = data.row_count;

    // Build preview table
    const thead = document.querySelector('#previewTable thead');
    const tbody = document.querySelector('#previewTable tbody');

    thead.innerHTML = '<tr>' + data.columns.map(col => `<th>${col}</th>`).join('') + '</tr>';
    tbody.innerHTML = data.preview.map(row =>
        '<tr>' + data.columns.map(col => `<td>${row[col] ?? ''}</td>`).join('') + '</tr>'
    ).join('');

    // Show auto-transform notice or manual mapping based on whether carrier has a transformer
    const autoNotice = document.getElementById('autoTransformNotice');
    const mappingSection = document.getElementById('mappingSection');

    if (hasTransformer) {
        autoNotice.classList.remove('hidden');
        mappingSection.classList.add('hidden');

        // Show available output types
        updateOutputTypesDisplay();
    } else {
        autoNotice.classList.add('hidden');
        mappingSection.classList.remove('hidden');
        buildMappingUI(data.columns);
        document.getElementById('fileTypeLabel').textContent = 'Commission Statement';
    }

    previewSection.classList.remove('hidden');
}

function updateOutputTypesDisplay() {
    const fileTypeLabel = document.getElementById('fileTypeLabel');

    if (availableOutputs.length === 0) {
        fileTypeLabel.textContent = 'Commission Statement';
        return;
    }

    if (availableOutputs.length === 1) {
        fileTypeLabel.textContent = availableOutputs[0].name;
    } else {
        // Multiple output types available
        const names = availableOutputs.map(o => o.name).join(', ');
        fileTypeLabel.textContent = `Multiple outputs available: ${names}`;
    }
}

function buildMappingUI(sourceColumns) {
    const grid = document.getElementById('mappingGrid');
    grid.innerHTML = '';

    templateColumns.forEach(targetCol => {
        const item = document.createElement('div');
        item.className = 'mapping-item';

        // Try to auto-match columns
        const autoMatch = findBestMatch(targetCol, sourceColumns);

        item.innerHTML = `
            <label>${targetCol}</label>
            <select data-target="${targetCol}">
                <option value="">-- Select --</option>
                ${sourceColumns.map(col =>
                    `<option value="${col}" ${col === autoMatch ? 'selected' : ''}>${col}</option>`
                ).join('')}
            </select>
        `;

        grid.appendChild(item);
    });
}

function findBestMatch(targetCol, sourceColumns) {
    const targetLower = targetCol.toLowerCase();

    // Exact match
    const exact = sourceColumns.find(col => col.toLowerCase() === targetLower);
    if (exact) return exact;

    // Partial match
    const partial = sourceColumns.find(col =>
        col.toLowerCase().includes(targetLower) || targetLower.includes(col.toLowerCase())
    );
    if (partial) return partial;

    // Common mappings
    const mappings = {
        'policyno': ['policy', 'policy_number', 'policynumber', 'pol_no', 'policy_no'],
        'phfirst': ['first', 'firstname', 'first_name', 'fname', 'insured_first'],
        'phlast': ['last', 'lastname', 'last_name', 'lname', 'insured_last'],
        'premium': ['prem', 'amount', 'premium_amount'],
        'effectivedate': ['effective', 'eff_date', 'effdate', 'start_date'],
        'termdate': ['term', 'termination', 'end_date', 'cancel_date'],
        'commreceived': ['commission', 'comm', 'comm_amt', 'commission_amount'],
        'writingagentid': ['agent', 'agentid', 'agent_id', 'writing_agent', 'producer'],
        'trandate': ['transaction_date', 'trans_date', 'date'],
        'state': ['st', 'state_code'],
        'issuer': ['carrier', 'company', 'insurance_company']
    };

    const targetMappings = mappings[targetLower];
    if (targetMappings) {
        for (const mapping of targetMappings) {
            const match = sourceColumns.find(col => col.toLowerCase().includes(mapping));
            if (match) return match;
        }
    }

    return null;
}

async function processFile() {
    showLoading(true);
    previewSection.classList.add('hidden');

    try {
        let data;

        if (hasTransformer && availableOutputs.length > 0) {
            // Process all available output types
            const outputTypes = availableOutputs.map(o => o.type);

            const response = await fetch('/api/process-all', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    saved_filename: savedFilename,
                    carrier_name: carrierName,
                    output_types: outputTypes
                })
            });

            data = await response.json();

            if (data.error) {
                throw new Error(data.error);
            }

            exportResults = data.results;
            showMultiExportSuccess(data);
        } else {
            // Single file processing (manual mapping or single output)
            let body = {
                saved_filename: savedFilename,
                carrier_name: carrierName,
                file_type: fileType,
                use_transformer: hasTransformer
            };

            // Add manual mappings if no transformer
            if (!hasTransformer) {
                const mappings = {};
                document.querySelectorAll('#mappingGrid select').forEach(select => {
                    const target = select.dataset.target;
                    const source = select.value;
                    if (source) {
                        mappings[target] = source;
                    }
                });
                body.column_mappings = mappings;
            }

            const response = await fetch('/api/process', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });

            data = await response.json();

            if (data.error) {
                throw new Error(data.error);
            }

            exportResults = [{ type: fileType, filename: data.export_filename, row_count: data.row_count }];
            showSingleExportSuccess(data);
        }

        showLoading(false);

    } catch (error) {
        showLoading(false);
        alert('Error processing file: ' + error.message);
        previewSection.classList.remove('hidden');
    }
}

function showSingleExportSuccess(data) {
    document.getElementById('exportFilename').textContent = data.export_filename;
    document.getElementById('exportRowCount').textContent = data.row_count;

    // Build download buttons
    const downloadContainer = document.getElementById('downloadButtons');
    downloadContainer.innerHTML = `
        <button class="btn btn-primary" onclick="downloadFile('${data.export_filename}')">
            Download ${fileType.charAt(0).toUpperCase() + fileType.slice(1)} File
        </button>
    `;

    // Show missing lookups warning if any
    showMissingLookupsWarning(data.missing_lookups);

    exportSection.classList.remove('hidden');
}

function showMultiExportSuccess(data) {
    const results = data.results;

    if (results.length === 0) {
        alert('No data to export');
        previewSection.classList.remove('hidden');
        return;
    }

    // Update summary
    const totalRows = results.reduce((sum, r) => sum + r.row_count, 0);
    document.getElementById('exportFilename').textContent = `${results.length} file(s) generated`;
    document.getElementById('exportRowCount').textContent = totalRows;

    // Build download buttons for each output type
    const downloadContainer = document.getElementById('downloadButtons');
    const outputNames = {
        'commission': 'Commission',
        'chargeback': 'Chargeback',
        'adjustment': 'Adjustment (Fees)'
    };

    downloadContainer.innerHTML = results.map(result => `
        <button class="btn btn-primary" onclick="downloadFile('${result.filename}')" style="margin: 0.5rem;">
            Download ${outputNames[result.type] || result.type} (${result.row_count} rows)
        </button>
    `).join('');

    // Add download all button if multiple files
    if (results.length > 1) {
        downloadContainer.innerHTML += `
            <button class="btn btn-secondary" onclick="downloadAllFiles()" style="margin: 0.5rem;">
                Download All
            </button>
        `;
    }

    // Show missing lookups warning if any
    showMissingLookupsWarning(data.missing_lookups);

    exportSection.classList.remove('hidden');
}

function showMissingLookupsWarning(missingLookups) {
    const warningDiv = document.getElementById('missingLookupsWarning');
    const lookupsList = document.getElementById('missingLookupsList');

    if (missingLookups && missingLookups.length > 0) {
        lookupsList.innerHTML = missingLookups.map(l => `<li>${l}</li>`).join('');
        warningDiv.classList.remove('hidden');
    } else {
        warningDiv.classList.add('hidden');
    }
}

function downloadFile(filename) {
    window.location.href = `/api/download/${filename}`;
}

function downloadAllFiles() {
    // Download each file with a small delay
    exportResults.forEach((result, index) => {
        setTimeout(() => {
            downloadFile(result.filename);
        }, index * 500);
    });
}

function showLoading(show) {
    if (show) {
        loading.classList.remove('hidden');
    } else {
        loading.classList.add('hidden');
    }
}

function resetUI() {
    currentFile = null;
    currentColumns = [];
    savedFilename = '';
    carrierName = '';
    fileType = 'commission';
    hasTransformer = false;
    availableOutputs = [];
    exportResults = [];
    fileInput.value = '';

    previewSection.classList.add('hidden');
    exportSection.classList.add('hidden');
    carrierModal.classList.add('hidden');
    document.getElementById('missingLookupsWarning').classList.add('hidden');
}
