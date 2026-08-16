from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def school_required(view_func):
    @login_required
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not getattr(request, "school", None):
            return redirect("signup")
        return view_func(request, *args, **kwargs)

    return wrapped
