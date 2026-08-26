def workspace(request):
    membership = None
    if request.user.is_authenticated:
        try:
            membership = request.user.talent_membership
        except AttributeError:
            pass
    return {
        "current_membership": membership,
        "current_organization": membership.organization if membership else None,
        "can_manage": membership.can_manage if membership else False,
    }
