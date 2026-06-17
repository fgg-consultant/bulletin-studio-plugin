from django.shortcuts import render


def index(request):
    return render(request, "bulletin_studio_plugin/index.html")
