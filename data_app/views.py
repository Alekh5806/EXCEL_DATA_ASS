from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["GET"])
def health_check(request):
    return Response(
        {
            "status": "ok",
            "message": "Excel Data Intelligence Chatbot backend is running.",
        }
    )

# Create your views here.
