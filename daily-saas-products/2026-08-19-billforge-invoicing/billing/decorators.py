from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from .models import Membership


def workspace_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")
        try:
            request.organization = request.user.billing_membership.organization
        except Membership.DoesNotExist:
            messages.error(request, "Your account is not connected to a billing workspace.")
            return redirect("landing")
        return view(request, *args, **kwargs)

    return wrapped
