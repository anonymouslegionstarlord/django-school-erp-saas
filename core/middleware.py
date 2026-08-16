from .models import Membership


def resolve_active_school(request):
    """Resolve and attach an authenticated user's active school membership."""
    request.school = None
    request.membership = None
    if not request.user.is_authenticated:
        return None
    memberships = Membership.objects.select_related("school").filter(
        user=request.user,
        is_active=True,
        school__is_active=True,
    )
    selected_id = request.session.get("active_school_id")
    membership = memberships.filter(school_id=selected_id).first() if selected_id else None
    membership = membership or memberships.first()
    if membership:
        request.school = membership.school
        request.membership = membership
        request.session["active_school_id"] = membership.school_id
    return membership


class ActiveSchoolMiddleware:
    """Attach the user's selected school to every authenticated request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        resolve_active_school(request)
        return self.get_response(request)
