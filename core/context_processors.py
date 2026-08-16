def school_context(request):
    return {
        "current_school": getattr(request, "school", None),
        "current_membership": getattr(request, "membership", None),
    }
