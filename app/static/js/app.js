// State
let currentFile = null;
let currentColumns = [];
let savedFilename = '';
let carrierName = '';

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
document.getElementById('downloadBtn').addEventListener('click', downloadExport);
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

        // Populate known carriers in modal
        populateCarrierList(data.known_carriers);

        if (data.recognized_carrier) {
            // Carrier recognized - auto-fill and ask for confirmation
            document.getElementById('carrierNameInput').value = data.recognized_carrier;
            document.getElementById('carrierModalMessage').textContent =
                `Recognized carrier: "${data.recognized_carrier}". Confirm or enter a different name:`;
        } else {
            // Unknown carrier - ask for name
            document.getElementById('carrierNameInput').value = '';
            document.getElementById('carrierModalMessage').textContent =
                'New file format detected. Please enter the carrier name:';
        }

        // Show carrier modal
        carrierModal.classList.remove('hidden');
        document.getElementById('carrierNameInput').focus();

        // Store preview data for later
        currentFile.previewData = data;

    } catch (error) {
        showLoading(false);
        alert('Error uploading file: ' + error.message);
    }
}

function populateCarrierList(carriers) {
    const datalist = document.getElementById('carrierList');
    datalist.innerHTML = '';
    carriers.forEach(carrier => {
        const option = document.createElement('option');
        option.value = carrier;
        datalist.appendChild(option);
    });
}

async function confirmCarrier() {
    const input = document.getElementById('carrierNameInput');
    carrierName = input.value.trim();

    if (!carrierName) {
        alert('Please enter a carrier name');
        return;
    }

    // Register carrier
    await fetch('/api/confirm-carrier', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            carrier_name: carrierName,
            saved_filename: savedFilename,
            columns: currentColumns,
            original_filename: currentFile.name
        })
    });

    carrierModal.classList.add('hidden');
    showPreview(currentFile.previewData);
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

    // Build column mapping UI
    buildMappingUI(data.columns);

    previewSection.classList.remove('hidden');
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
    // Gather column mappings
    const mappings = {};
    document.querySelectorAll('#mappingGrid select').forEach(select => {
        const target = select.dataset.target;
        const source = select.value;
        if (source) {
            mappings[target] = source;
        }
    });

    showLoading(true);
    previewSection.classList.add('hidden');

    try {
        const response = await fetch('/api/process', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                saved_filename: savedFilename,
                carrier_name: carrierName,
                column_mappings: mappings
            })
        });

        const data = await response.json();
        showLoading(false);

        if (data.error) {
            alert('Error: ' + data.error);
            previewSection.classList.remove('hidden');
            return;
        }

        // Show export success
        document.getElementById('exportFilename').textContent = data.export_filename;
        document.getElementById('exportRowCount').textContent = data.row_count;
        document.getElementById('downloadBtn').dataset.filename = data.export_filename;
        exportSection.classList.remove('hidden');

    } catch (error) {
        showLoading(false);
        alert('Error processing file: ' + error.message);
        previewSection.classList.remove('hidden');
    }
}

function downloadExport() {
    const filename = document.getElementById('downloadBtn').dataset.filename;
    window.location.href = `/api/download/${filename}`;
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
    fileInput.value = '';

    previewSection.classList.add('hidden');
    exportSection.classList.add('hidden');
    carrierModal.classList.add('hidden');
}
