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
    
    // Handle view toggle for check-in history
    const viewToggleButtons = document.querySelectorAll('.view-toggle');
    if (viewToggleButtons && viewToggleButtons.length > 0) {
        viewToggleButtons.forEach(button => {
            button.addEventListener('click', function(e) {
                e.preventDefault();
                
                // Get the view type from data attribute
                const viewType = this.dataset.view;
                
                // Get the current URL and update the 'view' parameter
                const url = new URL(this.href);
                
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
                
                // Update toggle button styles
                viewToggleButtons.forEach(btn => {
                    if (btn.dataset.view === viewType) {
                        btn.classList.remove('btn-outline-secondary');
                        btn.classList.add('btn-secondary');
                    } else {
                        btn.classList.remove('btn-secondary');
                        btn.classList.add('btn-outline-secondary');
                    }
                });
                
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
});

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
