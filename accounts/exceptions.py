"""
Standardized Exception Handler conforming to the API specification.
"""

from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


def custom_exception_handler(exc, context):
    """
    Transforms DRF default error responses into the unified ERP format:
    {
      "success": false,
      "message": "...",
      "errors": { ... }
    }
    """
    response = exception_handler(exc, context)

    if response is not None:
        data = response.data
        errors = {}
        message = "An error occurred."

        if isinstance(data, dict):
            if 'detail' in data:
                detail_val = data['detail']
                message = str(detail_val)
                errors['detail'] = detail_val
            else:
                message = "Validation failed."
                for key, val in data.items():
                    if isinstance(val, list):
                        errors[key] = [str(item) for item in val]
                    else:
                        errors[key] = [str(val)]
        elif isinstance(data, list):
            message = "Validation failed."
            errors['nonFieldErrors'] = [str(item) for item in data]
        else:
            message = str(data)
            errors['detail'] = str(data)

        # Custom tailored messages based on status codes
        if response.status_code == status.HTTP_401_UNAUTHORIZED:
            if not message or message == "An error occurred.":
                message = "Authentication credentials were not provided or are invalid."
        elif response.status_code == status.HTTP_403_FORBIDDEN:
            if not message or message == "An error occurred.":
                message = "You do not have permission to perform this action."
        elif response.status_code == status.HTTP_404_NOT_FOUND:
            if not message or message == "An error occurred.":
                message = "The requested resource was not found."

        response.data = {
            'success': False,
            'message': message,
            'errors': errors
        }

    return response
