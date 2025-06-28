/**
 * Validation utilities for form inputs and data
 */

// Validation rules with descriptive error messages
export const VALIDATION_RULES = {
  REQUIRED: 'This field is required',
  EMAIL: 'Please enter a valid email address',
  PHONE: 'Please enter a valid phone number',
  MIN_LENGTH: (min) => `Must be at least ${min} characters`,
  MAX_LENGTH: (max) => `Must not exceed ${max} characters`,
  MATCH: 'Fields do not match',
  PASSWORD: 'Password must contain at least 8 characters, including uppercase, lowercase and a number',
  URL: 'Please enter a valid URL'
};

/**
 * Validates that a value is not empty
 * @param {string|null|undefined} value - Value to validate
 * @returns {boolean} - True if valid
 */
export const isNotEmpty = (value) => {
  return value !== undefined && value !== null && String(value).trim() !== '';
};

/**
 * Validates email format
 * @param {string} email - Email to validate
 * @returns {boolean} - True if valid
 */
export const isValidEmail = (email) => {
  if (!email) return false;
  // More strict email validation
  const re = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
  const sanitizedEmail = String(email).toLowerCase().trim();
  return re.test(sanitizedEmail) && sanitizedEmail.length <= 254; // RFC 5321 length limit
};

/**
 * Validates phone number format (basic validation)
 * @param {string} phone - Phone to validate
 * @returns {boolean} - True if valid
 */
export const isValidPhone = (phone) => {
  const re = /^\+?[0-9]{10,15}$/;
  return re.test(String(phone).replace(/[\s()-]/g, ''));
};

/**
 * Validates password strength
 * @param {string} password - Password to validate
 * @returns {boolean} - True if valid
 */
export const isStrongPassword = (password) => {
  // At least 8 chars, 1 uppercase, 1 lowercase, 1 number
  const re = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$/;
  return re.test(String(password));
};

/**
 * Validates URL format
 * @param {string} url - URL to validate
 * @returns {boolean} - True if valid
 */
export const isValidUrl = (url) => {
  try {
    new URL(url);
    return true;
  } catch (e) {
    return false;
  }
};

/**
 * Validates if value meets minimum length
 * @param {string} value - Value to validate
 * @param {number} minLength - Minimum length
 * @returns {boolean} - True if valid
 */
export const meetsMinLength = (value, minLength) => {
  return value.length >= minLength;
};

/**
 * Validates if value meets maximum length
 * @param {string} value - Value to validate
 * @param {number} maxLength - Maximum length
 * @returns {boolean} - True if valid
 */
export const meetsMaxLength = (value, maxLength) => {
  return value.length <= maxLength;
};

/**
 * Sanitizes user input to prevent XSS
 * @param {string} input - Input to sanitize
 * @returns {string} - Sanitized input
 */
export const sanitizeInput = (input) => {
  if (input === null || input === undefined) return '';
  
  // Convert to string and trim
  const sanitized = String(input).trim();
  
  // Replace potentially dangerous characters
  return sanitized
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
    // Additional protection against script injection
    .replace(/javascript:/gi, '')
    .replace(/on\w+\s*=/gi, '');
};

/**
 * Form validator that returns errors for all fields
 * @param {Object} data - Form data to validate
 * @param {Object} rules - Validation rules
 * @returns {Object} - Object with errors for each field
 */
export const validateForm = (data, rules) => {
  const errors = {};
  
  Object.keys(rules).forEach(field => {
    const fieldRules = rules[field];
    const value = data[field];
    
    if (fieldRules.required && !isNotEmpty(value)) {
      errors[field] = VALIDATION_RULES.REQUIRED;
      return;
    }
    
    if (value) {
      if (fieldRules.email && !isValidEmail(value)) {
        errors[field] = VALIDATION_RULES.EMAIL;
      } else if (fieldRules.phone && !isValidPhone(value)) {
        errors[field] = VALIDATION_RULES.PHONE;
      } else if (fieldRules.minLength && !meetsMinLength(value, fieldRules.minLength)) {
        errors[field] = VALIDATION_RULES.MIN_LENGTH(fieldRules.minLength);
      } else if (fieldRules.maxLength && !meetsMaxLength(value, fieldRules.maxLength)) {
        errors[field] = VALIDATION_RULES.MAX_LENGTH(fieldRules.maxLength);
      } else if (fieldRules.password && !isStrongPassword(value)) {
        errors[field] = VALIDATION_RULES.PASSWORD;
      } else if (fieldRules.url && !isValidUrl(value)) {
        errors[field] = VALIDATION_RULES.URL;
      } else if (fieldRules.match && value !== data[fieldRules.match]) {
        errors[field] = VALIDATION_RULES.MATCH;
      }
    }
  });
  
  return errors;
};
