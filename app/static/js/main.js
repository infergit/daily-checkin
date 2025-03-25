// app/static/js/main.js
document.addEventListener('DOMContentLoaded', function() {
    console.log('Daily Check-in App loaded');

    // Handle project icon preview
    const iconInput = document.getElementById('icon');
    if (iconInput) {
        iconInput.addEventListener('input', function() {
            const iconPreview = this.previousElementSibling.querySelector('i');
            iconPreview.className = `bi bi-${this.value || 'check-circle'}`;
        });
    }
    
    // Handle project color preview
    const colorInput = document.getElementById('color');
    if (colorInput) {
        colorInput.addEventListener('input', function() {
            const colorPreview = document.getElementById('color-preview');
            colorPreview.style.backgroundColor = this.value || '#ffffff';
        });
    }
    
    // DASHBOARD CODE START - Merged from dashboard.js
    // Reference to important dashboard elements
    const projectTitle = document.querySelector('.card-header h3');
    const cardHeader = document.querySelector('.card-header');
    const projectSelect = document.getElementById('project_id');
    const noteField = document.getElementById('note');
    const csrfToken = document.querySelector('input[name="csrf_token"]')?.value;
    const checkinBtn = document.getElementById('checkin-btn');
    const checkinForm = document.querySelector('form');
    
    // Set up project selection change event
    if (projectSelect) {
        projectSelect.addEventListener('change', function() {
            const selectedProjectId = this.value;
            // Load project details
            loadProjectDetails(selectedProjectId);
            // Also update recent check-ins for the selected project
            updateRecentCheckins(selectedProjectId);
        });
    }
    
    // Handle check-in submission
    if (checkinBtn) {
        checkinBtn.addEventListener('click', function(e) {
            e.preventDefault();
            
            if (!noteField.value.trim()) {
                // Show warning in the correct style
                showFlashMessage('<div class="alert alert-warning">Please enter a note for your check-in</div>');
                return;
            }
            
            // Make AJAX request to submit check-in
            fetch('/checkin/api/checkin', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({
                    project_id: projectSelect.value,
                    note: noteField.value
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Show success message in the same style as project creation
                    showFlashMessage('<div class="alert alert-success">Check-in successful!</div>');
                    
                    // Clear the note field for next check-in
                    noteField.value = '';
                    
                    // Fetch updated recent check-ins
                    updateRecentCheckins(projectSelect.value);
                } else {
                    showFlashMessage(`<div class="alert alert-danger">Error: ${data.message}</div>`);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showFlashMessage('<div class="alert alert-danger">There was an error processing your check-in</div>');
            });
        });
    }
    
    // Function to display flash messages as centered floating overlays
    function showFlashMessage(htmlContent) {
        // Create overlay container if it doesn't exist
        let overlayContainer = document.getElementById('message-overlay');
        if (!overlayContainer) {
            // Create semi-transparent overlay
            overlayContainer = document.createElement('div');
            overlayContainer.id = 'message-overlay';
            
            // Style the overlay to cover the entire screen with center alignment
            Object.assign(overlayContainer.style, {
                position: 'fixed',
                top: '0',
                left: '0',
                width: '100%',
                height: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                backgroundColor: 'rgba(0, 0, 0, 0.2)',
                zIndex: '9999',
                pointerEvents: 'none' // Allow clicking through the overlay
            });
            
            document.body.appendChild(overlayContainer);
        }
        
        // Create a message box
        const messageBox = document.createElement('div');
        messageBox.style.pointerEvents = 'auto'; // Make the message clickable
        messageBox.style.minWidth = '300px';
        messageBox.style.maxWidth = '80%';
        messageBox.innerHTML = htmlContent;
        
        // Add the message to the overlay
        overlayContainer.appendChild(messageBox);
        
        // Make sure the alert has the dismiss button
        const alertDiv = messageBox.querySelector('.alert');
        if (alertDiv && !alertDiv.querySelector('.btn-close')) {
            alertDiv.classList.add('alert-dismissible', 'fade', 'show');
            const closeButton = document.createElement('button');
            closeButton.type = 'button';
            closeButton.className = 'btn-close';
            closeButton.setAttribute('aria-label', 'Close');
            
            // Add click handler to remove the entire overlay when close is clicked
            closeButton.addEventListener('click', function() {
                if (overlayContainer.parentNode) {
                    overlayContainer.remove();
                }
            });
            
            alertDiv.appendChild(closeButton);
        }
        
        // Setup automatic dismissal after 3 seconds
        setTimeout(() => {
            if (overlayContainer.parentNode) {
                overlayContainer.remove();
            }
        }, 3000);
    }
    // DASHBOARD CODE END
    
    // Handle view toggle for check-in history
    const viewToggleButtons = document.querySelectorAll('.view-toggle');
    if (viewToggleButtons && viewToggleButtons.length > 0) {
        viewToggleButtons.forEach(button => {
            button.addEventListener('click', function(e) {
                e.preventDefault();
                
                // Get the view type from data attribute
                const viewType = this.dataset.view;
                const url = this.dataset.url;
                
                // Update toggle button styles
                viewToggleButtons.forEach(btn => {
                    if (btn.dataset.view === viewType) {
                        btn.classList.remove('btn-outline-secondary');
                        btn.classList.add('btn-primary');
                    } else {
                        btn.classList.remove('btn-primary');
                        btn.classList.add('btn-outline-secondary');
                    }
                });
                
                // Show loading state
                const tableContainer = document.querySelector('#checkin-table-container');
                if (tableContainer) {
                    tableContainer.innerHTML = `
                        <div class="text-center py-5">
                            <div class="spinner-border" role="status">
                                <span class="visually-hidden">Loading...</span>
                            </div>
                            <p class="mt-2">Loading check-ins...</p>
                        </div>
                    `;
                }
                
                // Fetch the data
                fetch(url, {
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Update ONLY the table content
                        tableContainer.innerHTML = data.html;
                        
                        // Update URL without reloading the page
                        history.pushState({}, '', url);
                        
                        // Re-attach event listeners to new delete buttons
                        attachDeleteListeners();
                    } else {
                        showToast(data.message || 'Failed to load check-ins', 'danger');
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    showToast('Failed to load check-ins', 'danger');
                });
            });
        });
    }
    
    // Function to attach delete listeners (called on initial load and after view switch)
    function attachDeleteListeners() {
        const deleteForms = document.querySelectorAll('.delete-checkin-form');
        if (deleteForms && deleteForms.length > 0) {
            deleteForms.forEach(form => {
                // Remove existing listeners to avoid duplicates
                const newForm = form.cloneNode(true);
                form.parentNode.replaceChild(newForm, form);
                
                newForm.addEventListener('submit', function(e) {
                    // Prevent the default form submission
                    e.preventDefault();
                    
                    // Show confirmation dialog
                    if (confirm('Are you sure you want to delete this check-in?')) {
                        // If confirmed, submit the form programmatically as POST
                        const formData = new FormData(newForm);
                        
                        fetch(newForm.action, {
                            method: 'POST',
                            body: formData,
                            headers: {
                                'X-Requested-With': 'XMLHttpRequest'
                            }
                        })
                        .then(response => response.json())
                        .then(data => {
                            if (data.success) {
                                // Try to find parent element (could be a table row or a card)
                                const row = newForm.closest('tr') || newForm.closest('.card');
                                
                                if (row) {
                                    // Optional: Add fade-out animation
                                    row.style.transition = 'opacity 0.3s';
                                    row.style.opacity = '0';
                                    
                                    // Remove the row after animation completes
                                    setTimeout(() => {
                                        row.remove();
                                        
                                        // Check if table/container is now empty
                                        const container = document.querySelector('tbody') || document.querySelector('.d-md-none');
                                        
                                        if ((container && container.children.length === 0) || 
                                            (container.tagName === 'TBODY' && container.querySelectorAll('tr').length === 0)) {
                                            
                                            // Replace with "no records" message
                                            const tableContainer = document.querySelector('.table-responsive');
                                            if (tableContainer) {
                                                tableContainer.innerHTML = `
                                                    <div class="text-center py-4">
                                                        <p class="text-muted">No check-in records found for this project.</p>
                                                        <a href="${data.dashboardUrl}" class="btn btn-primary mt-2">
                                                            <i class="bi bi-check-circle"></i> Check In Now
                                                        </a>
                                                    </div>
                                                `;
                                            }
                                        }
                                        
                                        // Show success message
                                        showToast('Check-in deleted successfully', 'success');
                                    }, 300);
                                } else {
                                    // If we couldn't find the parent element, just reload the page
                                    showToast('Check-in deleted successfully. Refreshing...', 'success');
                                    setTimeout(() => window.location.reload(), 1000);
                                }
                            } else {
                                showToast(data.message || 'An error occurred', 'danger');
                            }
                        })
                        .catch(error => {
                            console.error('Error:', error);
                            showToast('Failed to delete check-in', 'danger');
                        });
                    }
                });
            });
        }
    }
    
    // Initial attachment of delete listeners
    attachDeleteListeners();

    // Handle automatic project switching on dropdown change
    const projectSelector = document.getElementById('project-selector');
    const projectSwitchBtn = document.getElementById('project-switch-btn');

    if (projectSelector && projectSwitchBtn) {
        // Hide the switch button when JavaScript is enabled
        projectSwitchBtn.style.display = 'none';
        
        // Add change event listener to automatically submit the form
        projectSelector.addEventListener('change', function() {
            // Get the form
            const form = this.closest('form');
            
            // Show a brief loading indicator in the select
            const originalText = projectSelector.options[projectSelector.selectedIndex].text;
            projectSelector.options[projectSelector.selectedIndex].text = 'Loading...';
            projectSelector.disabled = true;
            
            // For dashboard and history pages
            if (window.location.pathname.includes('/checkin/dashboard') || 
                window.location.pathname.includes('/checkin/history')) {
                
                // Redirect directly to the page with the selected project
                const selectedProject = projectSelector.value;
                const baseUrl = window.location.pathname.split('?')[0];
                window.location.href = `${baseUrl}?project=${selectedProject}`;
            } else {
                // For other pages, just submit the form normally
                form.submit();
            }
        });
    }

    // Other existing event handlers...
});

// Function to load project details via AJAX - moved outside the DOM ready event
function loadProjectDetails(projectId) {
    fetch(`/checkin/api/project/${projectId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Update project title and icon
                const projectTitle = document.querySelector('.card-header h3');
                if (projectTitle) {
                    projectTitle.innerHTML = '';
                    
                    if (data.project.icon) {
                        const icon = document.createElement('i');
                        icon.className = `bi bi-${data.project.icon} me-2`;
                        projectTitle.appendChild(icon);
                    }
                    
                    projectTitle.appendChild(document.createTextNode(data.project.name));
                }
                
                // Update header color if available
                const cardHeader = document.querySelector('.card-header');
                if (cardHeader && data.project.color) {
                    cardHeader.style.backgroundColor = data.project.color;
                } else if (cardHeader) {
                    cardHeader.style.backgroundColor = '';
                }
            } else {
                console.error('Error loading project details:', data.message);
                showFlashMessage('<div class="alert alert-danger">Error loading project details: ' + (data.message || '') + '</div>');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showFlashMessage('<div class="alert alert-danger">Failed to connect to server when loading project details</div>');
        });
}

// Function to update recent check-ins - moved outside the DOM ready event
function updateRecentCheckins(projectId) {
    console.log('Updating recent check-ins for project:', projectId);
    
    fetch(`/checkin/api/recent-checkins/${projectId}`)
        .then(response => {
            console.log('Recent check-ins response status:', response.status);
            return response.json();
        })
        .then(data => {
            console.log('Recent check-ins data:', data);
            
            if (data.success) {
                // Find the recent check-ins container using a more reliable selector
                const recentCheckinHeaders = document.querySelectorAll('.card-header h4');
                const recentCheckinsCard = document.getElementById('recent-checkins-card');
                
                if (!recentCheckinsCard) {
                    console.error('Could not find Recent Check-ins card');
                    return;
                }
                
                const cardBody = recentCheckinsCard.querySelector('.card-body');
                if (!cardBody) {
                    console.error('Could not find card body within Recent Check-ins card');
                    return;
                }
                
                // Save the existing history link if it exists
                const historyLink = cardBody.querySelector('a[href*="history"]');
                let historyLinkHtml = '';
                
                // Get the correct URL format from the existing link or create a reasonable default
                let historyUrl = '';
                if (historyLink) {
                    // Extract the base URL structure from the existing link
                    const currentHref = historyLink.getAttribute('href');
                    // Check if it uses query parameters (?project=) or path parameters (/project/)
                    if (currentHref.includes('?')) {
                        // Query parameter style URL
                        const baseUrl = currentHref.split('?')[0];
                        historyUrl = `${baseUrl}?project=${projectId}`;
                    } else {
                        // It might be using a path parameter
                        historyUrl = `/checkin/history?project=${projectId}`;
                    }
                    historyLinkHtml = `<div class="mt-3 text-center"><a href="${historyUrl}" class="btn btn-sm btn-outline-primary">View Full History</a></div>`;
                } else {
                    // Default to query parameter style which is more common in Flask
                    historyUrl = `/checkin/history?project=${projectId}`;
                    historyLinkHtml = `<div class="mt-3 text-center"><a href="${historyUrl}" class="btn btn-sm btn-outline-primary">View Full History</a></div>`;
                }
                
                if (data.recent_checkins && data.recent_checkins.length > 0) {
                    // We have check-ins to display
                    let html = '<ul class="list-group">';
                    
                    data.recent_checkins.forEach(check => {
                        html += `
                            <li class="list-group-item">
                                <strong>${check.check_time}</strong>
                                <p class="mb-0 small text-muted preserve-newlines">${check.note || ''}</p>
                            </li>
                        `;
                    });
                    
                    html += '</ul>';
                    html += historyLinkHtml;
                    
                    cardBody.innerHTML = html;
                } else {
                    // No check-ins
                    let html = '<p class="text-center">No recent check-ins yet.</p>';
                    html += historyLinkHtml;
                    
                    cardBody.innerHTML = html;
                }
            } else {
                console.error('Error fetching recent check-ins:', data.message);
            }
        })
        .catch(error => {
            console.error('Error updating recent check-ins:', error);
        });
}

// Simple toast notification function
function showToast(message, type = 'info') {
    // Create toast container if it doesn't exist
    let toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        toastContainer.className = 'position-fixed bottom-0 end-0 p-3';
        toastContainer.style.zIndex = '5';
        document.body.appendChild(toastContainer);
    }
    
    // Create toast element
    const toastId = 'toast-' + Date.now();
    const toastHtml = `
        <div id="${toastId}" class="toast align-items-center text-white bg-${type} border-0" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        </div>
    `;
    
    // Add toast to container
    toastContainer.insertAdjacentHTML('beforeend', toastHtml);
    
    // Initialize and show the toast
    const toastElement = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastElement, { autohide: true, delay: 3000 });
    toast.show();
    
    // Remove toast after it's hidden
    toastElement.addEventListener('hidden.bs.toast', function() {
        toastElement.remove();
    });
}
