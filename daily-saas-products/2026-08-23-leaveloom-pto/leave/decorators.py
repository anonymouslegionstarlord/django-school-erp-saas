from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect


def workspace_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")
        try:
            request.membership = request.user.leave_membership
            request.organization = request.membership.organization
        except AttributeError:
            messages.error(request, "Your account is not connected to a LeaveLoom workspace.")
            return redirect("logout")
        return view(request, *args, **kwargs)

    return wrapped
