"""
Custom domain exceptions for the application.
All exceptions inherit from CustomDomainException base class.
"""


class CustomDomainException(Exception):
    """
    Base exception for all domain-specific errors.

    Attributes:
        message (str): Human-readable error description
        code (str): Machine-readable error code for API responses
    """

    def __init__(self, message: str, code: str):
        self.message = message
        self.code = code
        super().__init__(message)


class EmailAlreadyExistsError(CustomDomainException):
    """Raised when attempting to add a duplicate email"""

    def __init__(self, message: str):
        message = "Email is already exists" if not message else message
        super().__init__(message=message, code="EMAIL_ALREADY_EXISTS")


class ProcessingError(CustomDomainException):
    """Raised when processing fails due to unexpected error"""

    def __init__(self, message: str = ""):
        message = (
            "Unable to process your request at this time. Please try again later."
            if not message
            else message
        )
        super().__init__(message=message, code="PROCESSING_ERROR")


class NotFoundError(CustomDomainException):
    """Raised when a requested resource is not found"""

    def __init__(self, message: str = ""):
        message = "The requested resource was not found." if not message else message
        super().__init__(message=message, code="NOT_FOUND")


class PermissionDeniedError(CustomDomainException):
    """Raised when a user does not have permission to access a resource"""

    def __init__(self, message: str = ""):
        message = "You do not have permission to access this resource." if not message else message
        super().__init__(message=message, code="PERMISSION_DENIED")


class AlreadyExistsError(CustomDomainException):
    """Raised when attempting to create a resource that already exists"""

    def __init__(self, message: str = ""):
        message = (
            "The resource you are trying to create already exists. " if not message else message
        )
        super().__init__(message=message, code="RESOURCE_EXISTS")



# Authentication & Credentials Exceptions


class InvalidCredentialsError(CustomDomainException):
    """Raised when email or password is incorrect"""

    def __init__(self, message: str = ""):
        message = (
            "The email or password you entered is incorrect. Please try again."
            if not message
            else message
        )
        super().__init__(message=message, code="INVALID_CREDENTIALS")


class InvalidTokenError(CustomDomainException):
    """Raised when a token is invalid or malformed"""

    def __init__(self, message: str = ""):
        message = "Your session is invalid. Please log in again." if not message else message
        super().__init__(message=message, code="INVALID_TOKEN")


class TokenExpiredError(CustomDomainException):
    """Raised when a token has expired"""

    def __init__(self, message: str = ""):
        message = (
            "Your session has expired. Please log in again to continue." if not message else message
        )
        super().__init__(message=message, code="TOKEN_EXPIRED")


class AccountInactiveError(CustomDomainException):
    """Raised when attempting to authenticate with an inactive account"""

    def __init__(self, message: str = ""):
        message = (
            "Your account has been deactivated. Please contact our support team for assistance."
            if not message
            else message
        )
        super().__init__(message=message, code="ACCOUNT_INACTIVE")


class AccountPendingApprovalError(CustomDomainException):
    """Raised when user tries to access features before account approval"""

    def __init__(self, message: str = ""):
        message = (
            "Your account is pending approval. "
            "You'll receive an email notification once your account is approved by our team."
            if not message
            else message
        )
        super().__init__(message=message, code="ACCOUNT_PENDING_APPROVAL")


class AccountUnverifiedError(CustomDomainException):
    """Raised when attempting to login with an unverified email"""

    def __init__(self, message: str = ""):
        message = (
            "Please verify your email address before logging in. "
            "Check your inbox for the verification link."
            if not message
            else message
        )
        super().__init__(message=message, code="ACCOUNT_UNVERIFIED")


class AccountLockedError(CustomDomainException):
    """Raised when account is locked due to too many failed login attempts"""

    def __init__(self, message: str = ""):
        message = (
            "Your account has been temporarily locked for security reasons. Please try again later."
            if not message
            else message
        )
        super().__init__(message=message, code="ACCOUNT_LOCKED")


# Rate Limiting & Throttling Exceptions


class RateLimitExceededError(CustomDomainException):
    """Raised when rate limit is exceeded"""

    def __init__(self, message: str = ""):
        message = "Too many requests. Please try again later." if not message else message
        super().__init__(message=message, code="RATE_LIMIT_EXCEEDED")


class TooManyAttemptsError(CustomDomainException):
    """Raised when too many attempts are made (login, OTP, etc.)"""

    def __init__(self, message: str = ""):
        message = "Too many attempts. Please try again later." if not message else message
        super().__init__(message=message, code="TOO_MANY_ATTEMPTS")


# Registration & Verification Exceptions


class InvalidOTPError(CustomDomainException):
    """Raised when OTP code is invalid or expired"""

    def __init__(self, message: str = ""):
        message = (
            "The code you entered is invalid or has expired. Please request a new one."
            if not message
            else message
        )
        super().__init__(message=message, code="INVALID_OTP")


class UserAlreadyRegisteredError(CustomDomainException):
    """Raised when attempting to register with an email that already exists"""

    def __init__(self, message: str = ""):
        message = "User with this email already exists" if not message else message
        super().__init__(message=message, code="USER_ALREADY_REGISTERED")


class RegistrationPendingError(CustomDomainException):
    """Raised when a pending registration already exists for an email"""

    def __init__(self, message: str = ""):
        message = (
            "A pending registration already exists for this email. "
            "Please check your inbox or try again later."
            if not message
            else message
        )
        super().__init__(message=message, code="REGISTRATION_PENDING")


# OAuth & Social Auth Exceptions


class OAuthFlowError(CustomDomainException):
    """Raised when OAuth authentication flow fails"""

    def __init__(self, message: str = "", provider: str = "OAuth"):
        message = (
            f"Unable to complete sign-in with {provider}. Please try again or use email login."
            if not message
            else message
        )
        super().__init__(message=message, code="OAUTH_FLOW_ERROR")


class OAuthStateInvalidError(CustomDomainException):
    """Raised when OAuth CSRF state validation fails"""

    def __init__(self, message: str = "", provider: str = "OAuth"):
        message = (
            "For your security, we need you to start the login process again. "
            "Please try signing in once more."
            if not message
            else message
        )
        super().__init__(message=message, code="OAUTH_STATE_INVALID")


class OAuthTokenInvalidError(CustomDomainException):
    """Raised when OAuth provider token is invalid"""

    def __init__(self, message: str = "", provider: str = "OAuth"):
        message = (
            f"We encountered an issue with {provider} authentication. Please try again."
            if not message
            else message
        )
        super().__init__(message=message, code="OAUTH_TOKEN_INVALID")


class MissingEmailError(CustomDomainException):
    """Raised when email is missing from OAuth provider response"""

    def __init__(self, message: str = "", provider: str = "OAuth"):
        message = (
            f"We couldn't retrieve your email from {provider}. "
            f"Please make sure your {provider} account has a verified email address."
            if not message
            else message
        )
        super().__init__(message=message, code="MISSING_EMAIL")


class MissingIDTokenError(CustomDomainException):
    """Raised when ID token is missing from OAuth response"""

    def __init__(self, message: str = "", provider: str = "OAuth"):
        message = (
            f"We didn't receive complete authentication information from {provider}. "
            f"Please try again."
            if not message
            else message
        )
        super().__init__(message=message, code="MISSING_ID_TOKEN")


class InvalidClientError(CustomDomainException):
    """Raised when OAuth client is invalid or not allowed"""

    def __init__(self, message: str = ""):
        message = (
            "There's an issue with the login request. Please try again." if not message else message
        )
        super().__init__(message=message, code="INVALID_CLIENT")


# Password Reset Exceptions


class InvalidResetCodeError(CustomDomainException):
    """Raised when password reset code is invalid or expired"""

    def __init__(self, message: str = ""):
        message = (
            "The reset code you entered is invalid or has expired. Please request a new one."
            if not message
            else message
        )
        super().__init__(message=message, code="INVALID_RESET_CODE")


class ResetTokenExpiredError(CustomDomainException):
    """Raised when password reset token has expired"""

    def __init__(self, message: str = ""):
        message = (
            "Your reset link has expired for security reasons. Please request a new password reset."
            if not message
            else message
        )
        super().__init__(message=message, code="RESET_TOKEN_EXPIRED")



class AuthenticationError(CustomDomainException):
    """Raised when authentication fails"""

    def __init__(self, message: str = ""):
        message = "Authentication failed. Please try again." if not message else message
        super().__init__(message=message, code="AUTHENTICATION_ERROR")


class OAuthTokenExchangeError(CustomDomainException):
    """Raised when OAuth token exchange fails"""

    def __init__(self, message: str = ""):
        message = (
            "Failed to exchange authorization code for tokens. Please try again."
            if not message
            else message
        )
        super().__init__(message=message, code="OAUTH_TOKEN_EXCHANGE_FAILED")


class OAuthTokenVerificationError(CustomDomainException):
    """Raised when OAuth token verification fails"""

    def __init__(self, message: str = ""):
        message = (
            "Failed to verify authentication token. Please try again." if not message else message
        )
        super().__init__(message=message, code="OAUTH_TOKEN_VERIFICATION_FAILED")


class PasswordReuseError(CustomDomainException):
    """Raised when user attempts to reuse a previously used password"""

    def __init__(self, message: str = ""):
        message = "New password cannot be the same as your old password" if not message else message
        super().__init__(message=message, code="PASSWORD_REUSE_ERROR")


class ValidationError(CustomDomainException):
    """Raised when input validation fails"""

    def __init__(self, message: str = "", code: str = "VALIDATION_ERROR"):
        message = "Input validation failed. Please check and try again." if not message else message
        super().__init__(message=message, code=code)


class ForbiddenError(CustomDomainException):
    """Raised when user is not allowed to access a resource"""

    def __init__(self, message: str = "", code: str = "FORBIDDEN"):
        message = "You are not allowed to perform this action." if not message else message
        super().__init__(message=message, code=code)


class LimitExceededError(CustomDomainException):
    """Raised when a limit is exceeded (likes, uploads, etc.)"""

    def __init__(self, message: str = "", code: str = "LIMIT_EXCEEDED"):
        message = "You have exceeded the limit. Please try again later." if not message else message
        super().__init__(message=message, code=code)


class BadRequestError(CustomDomainException):
    """Raised when the request is invalid or malformed"""

    def __init__(self, message: str = "", code: str = "BAD_REQUEST"):
        message = "The request is invalid. Please check your input and try again." if not message else message
        super().__init__(message=message, code=code)


class ConflictError(CustomDomainException):
    """Raised when there is a conflict with the current state (e.g., duplicate resource)"""

    def __init__(self, message: str = "", code: str = "CONFLICT"):
        message = "A conflict occurred. The resource may already exist." if not message else message
        super().__init__(message=message, code=code)
