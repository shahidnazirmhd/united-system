"""Custom project middleware.

Everything already in MIDDLEWARE (config/settings/base.py) before this
package existed — SecurityMiddleware, CorsMiddleware, CommonMiddleware,
GZipMiddleware — is third-party/Django's own. This package is where any
custom middleware this project needs lives, so "add a new one" always means
"add a file here + one line in settings," not "find wherever the last one
got dropped."
"""
