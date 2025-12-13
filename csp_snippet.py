
@app.after_request
def add_security_headers(response):
    """Add security headers to response"""
    # Content Security Policy
    # Allow scripts from self and inline (for now, until we move to external files)
    # Allow styles from self, inline, and Google Fonts
    # Allow fonts from self and Google Fonts
    csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "  # unsafe-eval needed for some libraries/legacy code
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "form-action 'self';"
    )
    response.headers['Content-Security-Policy'] = csp
    
    # Other security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    
    return response
