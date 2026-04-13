/**
 * EACIS Input Masking & Validation Utility
 * Standardizes user input formatting for premium feel and data integrity.
 */

const InputMask = {
    init() {
        document.addEventListener('input', (e) => {
            const el = e.target;
            
            // 1. Phone Number Masking (PH Format: 09XX XXX XXXX)
            if (el.name === 'phone' || el.classList.contains('mask-phone')) {
                this.maskPhone(el);
            }

            // 2. Postal Code Masking (PH Format: 4 digits)
            if (el.name === 'postal_code' || el.id === 'postal_code' || el.classList.contains('mask-postal')) {
                this.maskPostal(el);
            }

            // 3. Name Field Padding (No numbers allowed)
            if (el.name === 'first_name' || el.name === 'last_name' || el.name === 'full_name' || el.classList.contains('mask-name')) {
                this.maskName(el);
            }

            // 4. Numeric Only (Price/Stock)
            if (el.type === 'number' || el.classList.contains('mask-number')) {
                this.maskNumber(el);
            }
        });

        // Add visual validation state on blur
        document.addEventListener('blur', (e) => {
            const el = e.target;
            if (el.classList.contains('form-input') && el.required) {
                this.validateRequired(el);
            }
        }, true);
    },

    maskPhone(el) {
        let val = el.value.replace(/\D/g, ''); // Remove non-digits
        if (val.length > 11) val = val.substring(0, 11);
        
        let formatted = '';
        if (val.length > 0) {
            formatted = val.substring(0, 4);
            if (val.length > 4) {
                formatted += '-' + val.substring(4, 7);
            }
            if (val.length > 7) {
                formatted += '-' + val.substring(7, 11);
            }
        }
        el.value = formatted;
        
        // Simple valid state
        this.toggleValid(el, val.length === 11);
    },

    maskPostal(el) {
        let val = el.value.replace(/\D/g, '');
        if (val.length > 4) val = val.substring(0, 4);
        el.value = val;
        this.toggleValid(el, val.length === 4);
    },

    maskName(el) {
        // Remove digits and special characters commonly not in names
        const original = el.value;
        const cleaned = original.replace(/[0-9!@#$%^&*()_+={}\[\]:;"'<>,.?\/\\|`~]/g, '');
        if (original !== cleaned) {
            el.value = cleaned;
        }
    },

    maskNumber(el) {
        if (parseFloat(el.value) < 0) {
            el.value = 0;
        }
    },

    validateRequired(el) {
        const isValid = el.value.trim().length > 0;
        this.toggleValid(el, isValid);
    },

    toggleValid(el, isValid) {
        if (!el.value && !el.required) {
            el.style.borderColor = '';
            return;
        }
        el.style.borderColor = isValid ? 'var(--color-success)' : 'var(--color-danger)';
        if (!isValid) {
            el.style.boxShadow = '0 0 0 3px rgba(var(--color-danger-rgb), 0.1)';
        } else {
            el.style.boxShadow = '';
        }
    }
};

document.addEventListener('DOMContentLoaded', () => InputMask.init());
window.InputMask = InputMask;
