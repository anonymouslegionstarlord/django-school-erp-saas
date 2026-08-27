def workspace(request):
    if not request.user.is_authenticated:
        return {}
    membership = getattr(request, "membership", None)
    if membership is None:
        try:
            membership = request.user.spend_membership
        except AttributeError:
            return {}
    return {"membership": membership, "organization": membership.organization}
