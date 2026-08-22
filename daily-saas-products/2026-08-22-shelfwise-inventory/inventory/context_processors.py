def workspace(request):
    membership = None
    if request.user.is_authenticated:
        try:
            membership = request.user.stock_membership
        except AttributeError:
            pass
    return {"workspace_membership": membership}
