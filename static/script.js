// Global constant TOGGLE_URL is expected to be defined in the base template's <script> tag
// as the Flask url_for('toggle_dark_mode').

/**
 * Initializes theme icon and attaches event listener for theme toggling.
 * Sends the new state to the Flask server via the global TOGGLE_URL.
 */
function setupThemeToggle() {
    const body = document.body;
    const toggleButton = document.getElementById('theme-toggle');

    if (!toggleButton) return;

    // Helper to update the icon based on the current mode
    const updateIcon = (isDark) => {
        const iconElement = toggleButton.querySelector('i');
        if (iconElement) {
            iconElement.className = isDark ? 'fas fa-moon' : 'fas fa-sun';
        }
    };

    // Set initial icon state based on the class set by Jinja
    updateIcon(body.classList.contains('dark-mode'));

    // Theme Toggle Logic
    toggleButton.addEventListener('click', async() => {
        // 1. Toggle the class locally
        const isDark = body.classList.toggle('dark-mode');
        updateIcon(isDark);

        // 2. Send request to server to save preference
        if (typeof TOGGLE_URL !== 'undefined') {
            try {
                await fetch(TOGGLE_URL, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ dark_mode: isDark })
                });
            } catch (error) {
                console.error("Failed to save theme preference on server:", error);
            }
        }
    });
}

/**
 * Handles the profile dropdown logic for showing/hiding the menu.
 */
function setupProfileDropdown() {
    const profileDropdown = document.getElementById('profile-dropdown');
    if (profileDropdown) {
        const toggle = profileDropdown.querySelector('.dropdown-toggle');
        const menu = profileDropdown.querySelector('.dropdown-menu');

        if (toggle && menu) {
            toggle.addEventListener('click', () => {
                // Read aria-expanded to determine the current state
                const isExpanded = toggle.getAttribute('aria-expanded') === 'true';
                toggle.setAttribute('aria-expanded', !isExpanded);
                menu.classList.toggle('show');
            });

            // Close dropdown if the user clicks outside
            document.addEventListener('click', (event) => {
                if (!profileDropdown.contains(event.target)) {
                    menu.classList.remove('show');
                    toggle.setAttribute('aria-expanded', 'false');
                }
            });
        }
    }
}

/**
 * Handles showing/hiding signup fields in the combined auth form (auth.html).
 * @param {string} mode - 'login' or 'signup'
 */
function toggleAuthMode(mode) {
    const signupFields = document.getElementById('signup-fields');
    const authTitle = document.getElementById('auth-title');
    const switchLink = document.getElementById('auth-switch-link');
    const actionInput = document.getElementById('auth-action');
    const forgotPasswordLink = document.getElementById('forgot-password-link'); // Added reference

    if (signupFields && authTitle && switchLink && actionInput) {
        if (mode === 'signup') {
            signupFields.style.display = 'block';
            authTitle.textContent = 'Create Account';
            switchLink.innerHTML = 'Already have an account? <strong>Log In</strong>';
            actionInput.value = 'signup';
            // Hide forgot password link for signup
            if (forgotPasswordLink) {
                forgotPasswordLink.style.display = 'none';
            }
        } else { // 'login'
            signupFields.style.display = 'none';
            authTitle.textContent = 'Log In';
            switchLink.innerHTML = 'Need an account? <strong>Sign Up</strong>';
            actionInput.value = 'login';
            // Show forgot password link for login
            if (forgotPasswordLink) {
                forgotPasswordLink.style.display = 'block';
            }
        }
    }
}

/**
 * Sets up the auth page specific listeners (runs only on auth.html).
 */
function setupAuthPage() {
    const authPageElement = document.getElementById('auth-page');
    if (authPageElement) {
        // Start in login mode
        toggleAuthMode('login');

        // Attach listener for the switch link
        const switchLink = document.getElementById('auth-switch-link');
        let currentMode = 'login';
        if (switchLink) {
            switchLink.addEventListener('click', (e) => {
                e.preventDefault();
                currentMode = currentMode === 'login' ? 'signup' : 'login';
                toggleAuthMode(currentMode);
            });
        }
    }
}

/**
 * Sets up graceful fading for flash messages.
 */
function setupFlashMessages() {
    document.querySelectorAll('.flash').forEach(message => {
        setTimeout(() => {
            // Apply a transition style for smooth fade-out
            message.style.transition = 'opacity 0.5s ease-out';
            message.style.opacity = '0';

            // Wait for the transition to finish, then remove the element from DOM
            setTimeout(() => {
                message.remove();
            }, 500);
        }, 3000); // Start fade-out after 3 seconds
    });
}


// --- Main Execution Block ---
document.addEventListener('DOMContentLoaded', () => {
    // 1. Theme setup
    setupThemeToggle();

    // 2. Profile Dropdown setup
    setupProfileDropdown();

    // 3. Flash Messages setup
    setupFlashMessages();

    // 4. Auth page specific setup (conditional execution)
    setupAuthPage();
});