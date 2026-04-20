"""
Cookie Consent Frontend Example - Test Implementation

This file demonstrates how to implement the cookie consent banner using the new approach
that separates backend data from frontend UI implementation.
"""

import os
import json
import requests
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn

# Create a simple FastAPI app for testing
app = FastAPI(title="Cookie Consent Example")

# Set up templates
templates_dir = os.path.join(os.path.dirname(__file__), "test_templates")
os.makedirs(templates_dir, exist_ok=True)
templates = Jinja2Templates(directory=templates_dir)

# Set up static files
static_dir = os.path.join(os.path.dirname(__file__), "test_static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Create the CSS file with modern design elements
css_dir = os.path.join(static_dir, "css")
os.makedirs(css_dir, exist_ok=True)

with open(os.path.join(css_dir, "cookie-consent.css"), "w") as f:
    f.write("""
/* Modern Cookie Consent Banner CSS */
.cookie-consent-container {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 9999;
    padding: 1.5rem;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
}

.cookie-consent-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.5);
    backdrop-filter: blur(5px);
    z-index: 9998;
}

.cookie-consent-banner {
    /* Glassmorphism effect */
    background: rgba(255, 255, 255, 0.8);
    backdrop-filter: blur(10px);
    border-radius: 1rem;
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
    padding: 2rem;
    max-width: 1200px;
    margin: 0 auto;
    border: 1px solid rgba(255, 255, 255, 0.18);
    /* Background with subtle geometric shapes */
    background-image: 
        radial-gradient(circle at 20% 20%, rgba(79, 70, 229, 0.05) 0%, transparent 50%),
        radial-gradient(circle at 80% 80%, rgba(79, 70, 229, 0.05) 0%, transparent 50%);
}

.cookie-modal {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    z-index: 10000;
    width: 90%;
    max-width: 600px;
    max-height: 90vh;
    overflow-y: auto;
    /* Glassmorphism effect */
    background: rgba(255, 255, 255, 0.9);
    backdrop-filter: blur(10px);
    border-radius: 1rem;
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.15);
    padding: 2rem;
    border: 1px solid rgba(255, 255, 255, 0.18);
    /* Background with subtle geometric shapes */
    background-image: 
        radial-gradient(circle at 10% 10%, rgba(79, 70, 229, 0.05) 0%, transparent 40%),
        radial-gradient(circle at 90% 90%, rgba(79, 70, 229, 0.05) 0%, transparent 40%);
}

.cookie-consent-title {
    font-size: 1.5rem;
    font-weight: 700;
    margin-bottom: 1rem;
    color: #1f2937;
}

.cookie-consent-description {
    font-size: 1rem;
    line-height: 1.5;
    margin-bottom: 1.5rem;
    color: #4b5563;
}

.cookie-buttons {
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
    margin-top: 1.5rem;
}

.btn {
    padding: 0.75rem 1.5rem;
    border-radius: 0.5rem;
    font-weight: 600;
    font-size: 0.875rem;
    transition: all 0.2s ease;
    cursor: pointer;
    border: none;
    outline: none;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.btn-primary {
    /* Blue/indigo gradient */
    background: linear-gradient(135deg, #4F46E5 0%, #3730A3 100%);
    color: white;
    box-shadow: 0 4px 6px rgba(79, 70, 229, 0.3);
}

.btn-primary:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 15px rgba(79, 70, 229, 0.4);
}

.btn-secondary {
    background: transparent;
    color: #4b5563;
    box-shadow: inset 0 0 0 2px #e5e7eb;
}

.btn-secondary:hover {
    background: #f9fafb;
    color: #111827;
    box-shadow: inset 0 0 0 2px #d1d5db;
}

.cookie-category {
    margin-bottom: 1.5rem;
    padding: 1rem;
    border-radius: 0.5rem;
    background: rgba(249, 250, 251, 0.7);
}

.cookie-category-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.cookie-category-name {
    font-weight: 600;
    font-size: 1.1rem;
    color: #1f2937;
}

.cookie-category-toggle {
    display: flex;
    align-items: center;
}

.toggle-label {
    position: relative;
    display: inline-block;
    width: 3.5rem;
    height: 2rem;
}

.toggle-input {
    opacity: 0;
    width: 0;
    height: 0;
}

.toggle-slider {
    position: absolute;
    cursor: pointer;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: #e5e7eb;
    transition: .4s;
    border-radius: 1rem;
}

.toggle-slider:before {
    position: absolute;
    content: "";
    height: 1.5rem;
    width: 1.5rem;
    left: 0.25rem;
    bottom: 0.25rem;
    background-color: white;
    transition: .4s;
    border-radius: 50%;
}

.toggle-input:checked + .toggle-slider {
    background: linear-gradient(135deg, #4F46E5 0%, #3730A3 100%);
}

.toggle-input:checked + .toggle-slider:before {
    transform: translateX(1.5rem);
}

.toggle-input[disabled] + .toggle-slider {
    opacity: 0.5;
    cursor: not-allowed;
}

.cookie-category-description {
    margin-top: 0.5rem;
    font-size: 0.875rem;
    color: #6b7280;
    line-height: 1.4;
}

.hidden {
    display: none;
}

/* Powered by text */
.powered-by {
    font-size: 0.75rem;
    color: #9ca3af;
    text-align: center;
    margin-top: 1rem;
}

/* Responsive adjustments */
@media (max-width: 640px) {
    .cookie-buttons {
        flex-direction: column;
    }
    .btn {
        width: 100%;
    }
}
""")

# Create JavaScript file
js_dir = os.path.join(static_dir, "js")
os.makedirs(js_dir, exist_ok=True)

with open(os.path.join(js_dir, "cookie-consent.js"), "w") as f:
    f.write("""
/**
 * Modern Cookie Consent Implementation
 * This implements the cookie consent banner using the backend API
 */

class CookieConsent {
    constructor() {
        this.config = null;
        this.preferences = {
            necessary: true,
            preferences: false,
            statistics: false,
            marketing: false
        };
        this.consentGiven = false;
        this.initialized = false;
        this.bannerElement = null;
        this.modalElement = null;
        this.backdropElement = null;
    }

    /**
     * Initialize the cookie consent module
     */
    async init() {
        // First check if consent already exists in localStorage
        const savedConsent = this.getSavedConsent();
        if (savedConsent) {
            console.log('Consent already given:', savedConsent);
            this.preferences = savedConsent;
            this.consentGiven = true;
            return;
        }

        try {
            // Fetch configuration from the API
            const response = await fetch('/privacy/cookie-consent/config');
            this.config = await response.json();
            
            // Render the banner
            this.renderBanner();
            this.initialized = true;

            // Block page content if required by config
            if (this.config.settings.blockUntilConsent) {
                this.blockPageContent(true);
            }
        } catch (error) {
            console.error('Failed to initialize cookie consent:', error);
        }
    }

    /**
     * Get saved consent from localStorage
     */
    getSavedConsent() {
        try {
            const consent = localStorage.getItem('cookie_consent');
            if (consent) {
                const parsed = JSON.parse(consent);
                // Check if consent has expired
                if (parsed.expiry && new Date(parsed.expiry) > new Date()) {
                    return parsed.preferences;
                } else {
                    localStorage.removeItem('cookie_consent');
                }
            }
        } catch (e) {
            console.error('Error reading cookie consent from localStorage:', e);
            localStorage.removeItem('cookie_consent');
        }
        return null;
    }

    /**
     * Save consent to localStorage and backend
     */
    async saveConsent(acceptAll = false, rejectAll = false) {
        // Update preferences based on acceptAll/rejectAll flags
        if (acceptAll) {
            this.preferences = {
                necessary: true,
                preferences: true,
                statistics: true,
                marketing: true
            };
        } else if (rejectAll) {
            this.preferences = {
                necessary: true, // Necessary cookies can't be rejected
                preferences: false,
                statistics: false,
                marketing: false
            };
        }

        // Calculate expiry date
        const expiryDays = this.config?.settings?.consentExpiryDays || 180;
        const expiry = new Date();
        expiry.setDate(expiry.getDate() + expiryDays);

        // Save to localStorage
        localStorage.setItem('cookie_consent', JSON.stringify({
            preferences: this.preferences,
            expiry: expiry.toISOString()
        }));

        // Send to backend
        try {
            await fetch('/privacy/cookie-consent/record', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    necessary: this.preferences.necessary,
                    preferences: this.preferences.preferences,
                    statistics: this.preferences.statistics,
                    marketing: this.preferences.marketing,
                    accept_all: acceptAll,
                    reject_all: rejectAll
                })
            });
        } catch (error) {
            console.error('Failed to record consent:', error);
        }

        this.consentGiven = true;
        this.closeBanner();
        this.blockPageContent(false);
    }

    /**
     * Block or unblock page content
     */
    blockPageContent(block) {
        if (block && this.config?.settings?.blockUntilConsent) {
            document.body.style.overflow = 'hidden';
            if (!this.backdropElement) {
                this.backdropElement = document.createElement('div');
                this.backdropElement.className = 'cookie-consent-backdrop';
                document.body.appendChild(this.backdropElement);
            }
        } else {
            document.body.style.overflow = '';
            if (this.backdropElement) {
                this.backdropElement.remove();
                this.backdropElement = null;
            }
        }
    }

    /**
     * Render the cookie consent banner
     */
    renderBanner() {
        if (this.bannerElement) return;

        // Create banner element
        this.bannerElement = document.createElement('div');
        this.bannerElement.className = 'cookie-consent-container';
        
        // Add content to banner
        this.bannerElement.innerHTML = `
            <div class="cookie-consent-banner">
                <div class="cookie-consent-title">Your Privacy Matters</div>
                <div class="cookie-consent-description">
                    We use cookies to enhance your browsing experience, personalize content, 
                    and analyze our traffic. We also share information about your use of our site 
                    with our analytics partners.
                </div>
                <div class="cookie-buttons">
                    <button id="cookie-accept-all" class="btn btn-primary">Accept All</button>
                    <button id="cookie-reject-all" class="btn btn-secondary">Reject All</button>
                    <button id="cookie-customize" class="btn btn-secondary">Customize</button>
                </div>
                <div class="powered-by">Powered by Kaapi</div>
            </div>
        `;
        
        // Add to DOM
        document.body.appendChild(this.bannerElement);
        
        // Set up event listeners
        document.getElementById('cookie-accept-all').addEventListener('click', () => {
            this.saveConsent(true, false);
        });
        
        document.getElementById('cookie-reject-all').addEventListener('click', () => {
            this.saveConsent(false, true);
        });
        
        document.getElementById('cookie-customize').addEventListener('click', () => {
            this.showCustomizeModal();
        });
    }

    /**
     * Show the customize preferences modal
     */
    showCustomizeModal() {
        if (this.modalElement) return;
        
        // Create modal element
        this.modalElement = document.createElement('div');
        this.modalElement.className = 'cookie-modal';
        
        // Generate HTML for cookie categories
        let categoriesHtml = '';
        if (this.config && this.config.categories) {
            this.config.categories.forEach(category => {
                const isChecked = category.isNecessary || this.preferences[category.name.toLowerCase()];
                const isDisabled = category.isNecessary;
                
                categoriesHtml += `
                    <div class="cookie-category">
                        <div class="cookie-category-header">
                            <div class="cookie-category-name">${category.name}</div>
                            <div class="cookie-category-toggle">
                                <label class="toggle-label">
                                    <input type="checkbox" class="toggle-input" 
                                        data-category="${category.name.toLowerCase()}"
                                        ${isChecked ? 'checked' : ''}
                                        ${isDisabled ? 'disabled' : ''}>
                                    <span class="toggle-slider"></span>
                                </label>
                            </div>
                        </div>
                        <div class="cookie-category-description">${category.description}</div>
                    </div>
                `;
            });
        }
        
        // Add content to modal
        this.modalElement.innerHTML = `
            <div class="cookie-consent-title">Customize Cookie Preferences</div>
            <div class="cookie-consent-description">
                Select which cookies you want to accept. Necessary cookies help make the website usable
                and cannot be disabled.
            </div>
            <div class="cookie-categories">
                ${categoriesHtml}
            </div>
            <div class="cookie-buttons">
                <button id="cookie-save-preferences" class="btn btn-primary">Save Preferences</button>
            </div>
        `;
        
        // Add to DOM
        document.body.appendChild(this.modalElement);
        
        // Set up event listeners
        document.getElementById('cookie-save-preferences').addEventListener('click', () => {
            // Update preferences based on checkboxes
            const checkboxes = this.modalElement.querySelectorAll('.toggle-input');
            checkboxes.forEach(checkbox => {
                if (!checkbox.disabled) {
                    const category = checkbox.dataset.category;
                    this.preferences[category] = checkbox.checked;
                }
            });
            
            this.saveConsent();
        });
        
        // Hide the banner
        this.bannerElement.classList.add('hidden');
    }

    /**
     * Close the banner and modal
     */
    closeBanner() {
        if (this.bannerElement) {
            this.bannerElement.remove();
            this.bannerElement = null;
        }
        
        if (this.modalElement) {
            this.modalElement.remove();
            this.modalElement = null;
        }
        
        this.blockPageContent(false);
    }
}

// Initialize the cookie consent when the DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.cookieConsent = new CookieConsent();
    window.cookieConsent.init();
});
""")

# Create HTML template
with open(os.path.join(templates_dir, "index.html"), "w") as f:
    f.write("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cookie Consent Example</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link href="{{ url_for('static', path='/css/cookie-consent.css') }}" rel="stylesheet">
    <style>
        body {
            font-family: 'Inter', sans-serif;
            margin: 0;
            padding: 0;
            background: linear-gradient(135deg, #f5f7fa 0%, #e4e7eb 100%);
            min-height: 100vh;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
        }
        header {
            text-align: center;
            margin-bottom: 2rem;
        }
        h1 {
            color: #1f2937;
            font-weight: 700;
            font-size: 2rem;
        }
        .content {
            background: rgba(255, 255, 255, 0.8);
            backdrop-filter: blur(10px);
            border-radius: 1rem;
            padding: 2rem;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.18);
        }
        .section {
            margin-bottom: 2rem;
        }
        h2 {
            color: #4F46E5;
            font-weight: 600;
            margin-bottom: 1rem;
        }
        p {
            color: #4b5563;
            line-height: 1.6;
        }
        .card {
            background: rgba(255, 255, 255, 0.7);
            border-radius: 0.75rem;
            padding: 1.5rem;
            margin-bottom: 1rem;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .card h3 {
            margin-top: 0;
            color: #1f2937;
        }
        pre {
            background: #f3f4f6;
            padding: 1rem;
            border-radius: 0.5rem;
            overflow-x: auto;
            font-size: 0.875rem;
        }
        .footer {
            text-align: center;
            margin-top: 3rem;
            color: #6b7280;
            font-size: 0.875rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Cookie Consent Example</h1>
            <p>Modern implementation with a frontend-backend separation</p>
        </header>
        
        <div class="content">
            <div class="section">
                <h2>Overview</h2>
                <p>
                    This example demonstrates how to implement a modern cookie consent banner with complete
                    separation between backend data management and frontend UI implementation.
                </p>
                <p>
                    The backend API provides only essential configuration data, while the frontend has
                    complete control over the design and user experience.
                </p>
            </div>
            
            <div class="section">
                <h2>Backend API Response</h2>
                <p>The backend provides a simple API endpoint that returns cookie consent configuration:</p>
                <div class="card">
                    <h3>GET /privacy/cookie-consent/config</h3>
                    <pre id="api-response">Loading API response...</pre>
                </div>
            </div>
            
            <div class="section">
                <h2>Design Elements</h2>
                <p>The implementation includes modern design elements:</p>
                <div class="card">
                    <h3>Glassmorphism Effect</h3>
                    <p>Semi-transparent backgrounds with backdrop blur for a modern look.</p>
                </div>
                <div class="card">
                    <h3>Gradient Backgrounds</h3>
                    <p>Blue/indigo gradient color scheme with subtle geometric shapes.</p>
                </div>
                <div class="card">
                    <h3>Interactive Elements</h3>
                    <p>Buttons with hover effects and smooth transitions.</p>
                </div>
            </div>
            
            <div class="section">
                <h2>User Preferences</h2>
                <p>Current cookie preferences (if set):</p>
                <pre id="current-preferences">No preferences set yet</pre>
            </div>
        </div>
        
        <div class="footer">
            &copy; 2025 Kaapi - Privacy Compliance Plugin Example
        </div>
    </div>

    <script src="{{ url_for('static', path='/js/cookie-consent.js') }}"></script>
    <script>
        // Display the API response
        fetch('/privacy/cookie-consent/config')
            .then(response => response.json())
            .then(data => {
                document.getElementById('api-response').textContent = JSON.stringify(data, null, 2);
            })
            .catch(error => {
                document.getElementById('api-response').textContent = 'Error loading API response: ' + error.message;
            });
            
        // Check for existing preferences
        document.addEventListener('DOMContentLoaded', () => {
            setTimeout(() => {
                const savedConsent = localStorage.getItem('cookie_consent');
                if (savedConsent) {
                    try {
                        const parsed = JSON.parse(savedConsent);
                        document.getElementById('current-preferences').textContent = JSON.stringify(parsed.preferences, null, 2);
                    } catch (e) {
                        console.error('Error parsing saved consent:', e);
                    }
                }
            }, 1000); // Wait for cookie consent to initialize
        });
    </script>
</body>
</html>
""")

# Create API route for the test page
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Test page with the cookie consent example"""
    return templates.TemplateResponse("index.html", {"request": request})

# Mock API endpoint for cookie consent config
@app.get("/privacy/cookie-consent/config")
async def mock_cookie_consent_config():
    """Mock endpoint that returns cookie consent configuration"""
    return {
        "settings": {
            "consentExpiryDays": 180,
            "blockUntilConsent": False
        },
        "categories": [
            {
                "id": 1,
                "name": "Necessary",
                "description": "These cookies are essential for the website to function properly.",
                "isNecessary": True
            },
            {
                "id": 2,
                "name": "Preferences",
                "description": "These cookies allow the website to remember choices you make and provide enhanced features.",
                "isNecessary": False
            },
            {
                "id": 3,
                "name": "Statistics",
                "description": "These cookies collect information about how you use the website, which pages you visited and which links you clicked on.",
                "isNecessary": False
            },
            {
                "id": 4,
                "name": "Marketing",
                "description": "These cookies are used to track visitors across websites to display relevant advertisements.",
                "isNecessary": False
            }
        ],
        "version": "1.0"
    }

# Mock API endpoint for recording cookie consent
@app.post("/privacy/cookie-consent/record", status_code=201)
async def mock_cookie_consent_record(request: Request):
    """Mock endpoint that records cookie consent preferences"""
    try:
        body = await request.json()
        print("Received cookie consent preferences:", body)
        return {"status": "success"}
    except Exception as e:
        print("Error recording cookie consent:", str(e))
        return {"status": "error", "message": str(e)}

def run_test_server():
    """Run the test server"""
    print("Starting cookie consent test server...")
    print("Visit http://localhost:8000 to see the example")
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    run_test_server()
