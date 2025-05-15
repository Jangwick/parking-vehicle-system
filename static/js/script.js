document.addEventListener('DOMContentLoaded', function() {
    // Parking slot selection logic
    const parkingSlots = document.querySelectorAll('.parking-slot');
    if (parkingSlots.length > 0) {
        parkingSlots.forEach(slot => {
            slot.addEventListener('click', function() {
                // Deselect all slots
                parkingSlots.forEach(s => s.classList.remove('selected'));
                
                // Select this slot
                this.classList.add('selected');
                
                // Update the hidden slot_id input
                document.getElementById('slot_id').value = this.dataset.slotId;
            });
        });
    }
    
    // Reservation form validation
    const reservationForm = document.getElementById('reservationForm');
    if (reservationForm) {
        reservationForm.addEventListener('submit', function(event) {
            const startTime = new Date(document.getElementById('start_time').value);
            const endTime = new Date(document.getElementById('end_time').value);
            const slotId = document.getElementById('slot_id').value;
            
            if (!slotId) {
                event.preventDefault();
                showAlert('Please select a parking slot');
                return;
            }
            
            if (startTime >= endTime) {
                event.preventDefault();
                showAlert('End time must be after start time');
                return;
            }
            
            if (startTime < new Date()) {
                event.preventDefault();
                showAlert('Start time cannot be in the past');
                return;
            }
        });
    }
    
    // Real-time availability refresh
    const refreshButton = document.getElementById('refresh-availability');
    if (refreshButton) {
        refreshButton.addEventListener('click', function() {
            refreshAvailability();
        });
    }
    
    // Filter slots based on vehicle type
    const vehicleTypeFilter = document.getElementById('vehicleTypeFilter');
    if (vehicleTypeFilter) {
        vehicleTypeFilter.addEventListener('change', function() {
            filterSlots(this.value);
        });
    }
    
    // Admin dashboard charts initialization
    initializeCharts();
    
    // Initialize tooltips and popovers
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    });
    
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'))
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl)
    });
});

function showAlert(message) {
    const alertDiv = document.createElement('div');
    alertDiv.className = 'alert alert-danger alert-dismissible fade show';
    alertDiv.role = 'alert';
    
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    const container = document.querySelector('.container');
    container.insertBefore(alertDiv, container.firstChild);
    
    // Auto dismiss after 5 seconds
    setTimeout(() => {
        const bsAlert = new bootstrap.Alert(alertDiv);
        bsAlert.close();
    }, 5000);
}

function refreshAvailability() {
    fetch('/api/slots/available')
        .then(response => response.json())
        .then(data => {
            const availableContainer = document.getElementById('available-slots');
            availableContainer.innerHTML = '';
            
            if (data.length === 0) {
                availableContainer.innerHTML = '<p class="text-center">No available slots found</p>';
                return;
            }
            
            data.forEach(slot => {
                const slotElement = document.createElement('div');
                slotElement.className = `parking-slot slot-${slot.slot_type.toLowerCase()}`;
                slotElement.dataset.slotId = slot.id;
                
                slotElement.innerHTML = `
                    <h5>Slot ${slot.slot_number}</h5>
                    <p>Type: ${slot.slot_type}</p>
                `;
                
                availableContainer.appendChild(slotElement);
            });
            
            // Re-attach click events
            document.querySelectorAll('.parking-slot').forEach(slot => {
                slot.addEventListener('click', function() {
                    document.querySelectorAll('.parking-slot').forEach(s => s.classList.remove('selected'));
                    this.classList.add('selected');
                    document.getElementById('slot_id').value = this.dataset.slotId;
                });
            });
        })
        .catch(error => {
            console.error('Error fetching available slots:', error);
            showAlert('Failed to refresh availability. Please try again.');
        });
}

function filterSlots(type) {
    const slots = document.querySelectorAll('.parking-slot');
    
    slots.forEach(slot => {
        if (type === 'all' || slot.classList.contains(`slot-${type.toLowerCase()}`)) {
            slot.style.display = 'block';
        } else {
            slot.style.display = 'none';
        }
    });
}

function initializeCharts() {
    // Only initialize charts if we're on the admin dashboard
    const reservationChart = document.getElementById('reservationChart');
    if (!reservationChart) return;
    
    // Sample chart data - in a real app, this would come from backend
    const ctx = reservationChart.getContext('2d');
    const myChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'],
            datasets: [{
                label: 'Reservations',
                data: [12, 19, 3, 5, 2, 3, 9],
                backgroundColor: '#3498db'
            }]
        },
        options: {
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
    
    // Vehicle type distribution chart
    const vehicleChartEl = document.getElementById('vehicleChart');
    if (vehicleChartEl) {
        const vehicleCtx = vehicleChartEl.getContext('2d');
        const vehicleChart = new Chart(vehicleCtx, {
            type: 'pie',
            data: {
                labels: ['Gasoline', 'Diesel', 'Electric'],
                datasets: [{
                    data: [30, 50, 20],
                    backgroundColor: ['#3498db', '#e74c3c', '#2ecc71']
                }]
            }
        });
    }
}

// Ensure proper JSON format and headers in fetch requests
// For example:

function apiCall(endpoint, data) {
    return fetch(endpoint, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(data)  // Make sure data is properly serialized 
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => {
                throw new Error(err.message || 'Something went wrong');
            });
        }
        return response.json();
    })
    .catch(error => {
        console.error('API Error:', error);
        // Handle error appropriately
    });
}
